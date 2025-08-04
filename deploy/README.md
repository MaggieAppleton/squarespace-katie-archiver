# Production Deployment Guide

This directory contains production deployment tools and configurations for the Squarespace Blog Archiver.

## Quick Start

1. **Prerequisites**

   ```bash
   # Install Docker and Docker Compose
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

2. **Deploy**

   ```bash
   # Run the deployment script
   ./deploy/scripts/deploy.sh
   ```

3. **Monitor**

   ```bash
   # Check status
   ./deploy/scripts/deploy.sh status

   # View logs
   ./deploy/scripts/deploy.sh logs
   ```

## Directory Structure

```
deploy/
├── docker/
│   ├── Dockerfile              # Production Docker image
│   ├── docker-compose.yml      # Container orchestration
│   └── config/                 # Runtime configuration
├── scripts/
│   └── deploy.sh              # Deployment automation script
├── config/
│   └── production.json        # Production configuration template
└── README.md                  # This file
```

## Configuration

### Environment Variables

- `ARCHIVER_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `ARCHIVER_OUTPUT_DIR` - Output directory path
- `ARCHIVER_CONFIG_FILE` - Custom configuration file path

### Production Configuration

The `config/production.json` file contains optimized settings for production:

- **Rate Limiting**: 3-second delays between requests
- **Memory Management**: 1.5GB memory limit with monitoring
- **Performance**: Optimized batch sizes and caching
- **Logging**: Structured logging with rotation
- **Monitoring**: Progress reports and performance metrics

## Deployment Commands

```bash
# Deploy or update
./deploy/scripts/deploy.sh deploy

# Stop services
./deploy/scripts/deploy.sh stop

# Restart services
./deploy/scripts/deploy.sh restart

# View logs
./deploy/scripts/deploy.sh logs

# Check status
./deploy/scripts/deploy.sh status
```

## Monitoring and Maintenance

### Health Checks

The deployment includes automatic health checks:

- Container health status
- Application connectivity
- Resource usage monitoring

### Log Management

Logs are automatically rotated and stored in:

- Container logs: `docker logs squarespace-archiver`
- Application logs: `/app/logs/` (mounted volume)
- Deployment logs: `/var/log/archiver-deploy.log`

### Performance Monitoring

Performance reports are generated automatically:

- Memory usage tracking
- CPU utilization monitoring
- Operation timing statistics
- Cache effectiveness metrics

### Backup Strategy

Automated backups include:

- Archive outputs (with timestamps)
- Configuration files
- Performance reports
- Application state

## Scaling

For larger deployments:

1. **Enable Redis Caching**

   ```bash
   docker-compose --profile cache up -d
   ```

2. **Adjust Resource Limits**

   ```yaml
   # In docker-compose.yml
   memory: 4g
   cpus: "2.0"
   ```

3. **Configure Load Balancing**
   ```bash
   # Run multiple instances
   docker-compose up -d --scale archiver=3
   ```

## Security

Production security measures:

- Non-root container user
- Read-only configuration mounts
- Resource limits and quotas
- Health check endpoints
- Secure logging practices

## Troubleshooting

### Common Issues

1. **Container Won't Start**

   ```bash
   docker logs squarespace-archiver
   # Check configuration and dependencies
   ```

2. **High Memory Usage**

   ```bash
   # Check performance reports
   docker exec squarespace-archiver cat /app/output/performance_report.json
   ```

3. **Network Connectivity**
   ```bash
   # Test connectivity
   docker exec squarespace-archiver python -m src.main test-connectivity
   ```

### Resource Monitoring

```bash
# Monitor resource usage
docker stats squarespace-archiver

# Check disk usage
docker exec squarespace-archiver df -h

# Monitor memory usage
docker exec squarespace-archiver free -m
```

## Updates

To update the archiver:

1. **Pull Latest Code**

   ```bash
   git pull origin main
   ```

2. **Rebuild and Deploy**

   ```bash
   ./deploy/scripts/deploy.sh
   ```

3. **Verify Update**
   ```bash
   ./deploy/scripts/deploy.sh status
   ```

## Support

For production support:

- Check logs first: `./deploy/scripts/deploy.sh logs`
- Review performance reports in output directory
- Monitor system resources
- Check application health status

## Best Practices

1. **Regular Monitoring**: Check logs and performance reports daily
2. **Resource Planning**: Monitor memory and CPU usage trends
3. **Backup Verification**: Regularly verify backup integrity
4. **Configuration Management**: Version control all configuration changes
5. **Update Schedule**: Plan regular updates during maintenance windows
