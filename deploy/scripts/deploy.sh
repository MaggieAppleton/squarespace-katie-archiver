#!/bin/bash
# Production deployment script for Squarespace Blog Archiver

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/archiver-deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}ERROR: $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check if we have the required files
    if [[ ! -f "$PROJECT_DIR/requirements.txt" ]]; then
        error "requirements.txt not found in project directory"
    fi
    
    if [[ ! -f "$PROJECT_DIR/archiver_config.json" ]]; then
        warning "archiver_config.json not found. Creating default config..."
        cd "$PROJECT_DIR"
        python -m src.main create-config
    fi
    
    success "Prerequisites check completed"
}

# Build Docker image
build_image() {
    log "Building Docker image..."
    
    cd "$PROJECT_DIR"
    docker build -f deploy/docker/Dockerfile -t squarespace-archiver:latest .
    
    if [[ $? -eq 0 ]]; then
        success "Docker image built successfully"
    else
        error "Failed to build Docker image"
    fi
}

# Deploy with Docker Compose
deploy() {
    log "Deploying with Docker Compose..."
    
    cd "$DEPLOY_DIR/docker"
    
    # Create config directory if it doesn't exist
    mkdir -p config
    
    # Copy configuration file
    if [[ -f "$PROJECT_DIR/archiver_config.json" ]]; then
        cp "$PROJECT_DIR/archiver_config.json" config/
        log "Configuration file copied"
    fi
    
    # Start services
    docker-compose up -d
    
    if [[ $? -eq 0 ]]; then
        success "Services deployed successfully"
    else
        error "Failed to deploy services"
    fi
}

# Run health checks
health_check() {
    log "Running health checks..."
    
    # Wait for services to start
    sleep 10
    
    # Check if container is running
    if docker ps | grep -q "squarespace-archiver"; then
        success "Archiver container is running"
    else
        error "Archiver container is not running"
    fi
    
    # Check container health
    health_status=$(docker inspect --format='{{.State.Health.Status}}' squarespace-archiver 2>/dev/null || echo "unknown")
    
    if [[ "$health_status" == "healthy" ]]; then
        success "Container health check passed"
    elif [[ "$health_status" == "starting" ]]; then
        warning "Container is still starting up"
    else
        warning "Container health status: $health_status"
    fi
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Create systemd service for monitoring (optional)
    cat > /tmp/archiver-monitor.service << EOF
[Unit]
Description=Squarespace Archiver Monitor
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'docker ps | grep squarespace-archiver || docker-compose -f $DEPLOY_DIR/docker/docker-compose.yml up -d'
WorkingDirectory=$DEPLOY_DIR/docker

[Install]
WantedBy=multi-user.target
EOF
    
    if [[ -w /etc/systemd/system/ ]]; then
        sudo mv /tmp/archiver-monitor.service /etc/systemd/system/
        sudo systemctl enable archiver-monitor.service
        success "Monitoring service installed"
    else
        warning "Could not install systemd monitoring service (insufficient permissions)"
    fi
}

# Setup log rotation
setup_log_rotation() {
    log "Setting up log rotation..."
    
    cat > /tmp/archiver-logrotate << EOF
/var/log/archiver-deploy.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
    
    if [[ -w /etc/logrotate.d/ ]]; then
        sudo mv /tmp/archiver-logrotate /etc/logrotate.d/archiver
        success "Log rotation configured"
    else
        warning "Could not configure log rotation (insufficient permissions)"
    fi
}

# Main deployment function
main() {
    log "Starting deployment of Squarespace Blog Archiver"
    log "Project directory: $PROJECT_DIR"
    log "Deploy directory: $DEPLOY_DIR"
    
    check_prerequisites
    build_image
    deploy
    health_check
    setup_monitoring
    setup_log_rotation
    
    success "Deployment completed successfully!"
    
    echo ""
    echo "=== Deployment Information ==="
    echo "Docker containers:"
    docker ps | grep archiver
    echo ""
    echo "To view logs: docker logs squarespace-archiver"
    echo "To stop: cd $DEPLOY_DIR/docker && docker-compose down"
    echo "To update: $0"
    echo ""
    
    log "Deployment script completed"
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log "Stopping services..."
        cd "$DEPLOY_DIR/docker"
        docker-compose down
        success "Services stopped"
        ;;
    "restart")
        log "Restarting services..."
        cd "$DEPLOY_DIR/docker"
        docker-compose restart
        success "Services restarted"
        ;;
    "logs")
        docker logs -f squarespace-archiver
        ;;
    "status")
        docker ps | grep archiver
        ;;
    "help")
        echo "Usage: $0 [deploy|stop|restart|logs|status|help]"
        echo "  deploy  - Deploy the archiver (default)"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - Show container logs"
        echo "  status  - Show container status"
        echo "  help    - Show this help message"
        ;;
    *)
        error "Unknown command: $1. Use '$0 help' for usage information."
        ;;
esac