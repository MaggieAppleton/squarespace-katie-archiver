"""Main entry point for the Squarespace Blog Archiver."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from .config import ConfigManager, ArchiveConfig
from .logger import setup_logging, get_default_log_file
from .connectivity import ConnectivityChecker


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--log-level', '-l', default='INFO', 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              help='Logging level')
@click.option('--log-file', type=click.Path(), help='Log file path')
@click.option('--no-console', is_flag=True, help='Disable console output')
@click.pass_context
def cli(ctx, config, log_level, log_file, no_console):
    """Squarespace Blog Archiver - Backup and preserve your blog content."""
    
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Load configuration
    config_path = Path(config) if config else None
    ctx.obj['config'] = ConfigManager.load_config(config_path)
    
    # Set up logging
    log_file_path = Path(log_file) if log_file else get_default_log_file()
    logger = setup_logging(
        log_level=log_level,
        log_file=log_file_path,
        console_output=not no_console
    )
    
    ctx.obj['logger'] = logger
    logger.info("Squarespace Blog Archiver started")
    logger.info(f"Target site: {ctx.obj['config'].site_url}")


@cli.command()
@click.pass_context
def test_connectivity(ctx):
    """Test connectivity to the target site."""
    config: ArchiveConfig = ctx.obj['config']
    logger = ctx.obj['logger']
    
    logger.info("Starting connectivity tests...")
    
    checker = ConnectivityChecker(config)
    
    # Basic connectivity test
    logger.info("=" * 50)
    logger.info("BASIC CONNECTIVITY TEST")
    logger.info("=" * 50)
    
    basic_result = checker.check_basic_connectivity()
    if basic_result['success']:
        logger.info("✓ Basic connectivity: PASSED")
        logger.info(f"  Status Code: {basic_result['status_code']}")
        logger.info(f"  Response Time: {basic_result['response_time']:.2f}s")
        logger.info(f"  Content Length: {basic_result['content_length']} bytes")
        logger.info(f"  Content Type: {basic_result['content_type']}")
    else:
        logger.error("✗ Basic connectivity: FAILED")
        logger.error(f"  Error: {basic_result['error']}")
        return
    
    # JavaScript rendering test
    logger.info("=" * 50)
    logger.info("JAVASCRIPT RENDERING TEST")
    logger.info("=" * 50)
    
    async def run_js_test():
        js_result = await checker.check_javascript_rendering()
        if js_result['success']:
            logger.info("✓ JavaScript rendering: PASSED")
            logger.info(f"  Page Title: {js_result['title']}")
            logger.info(f"  Content Length: {js_result['content_length']} bytes")
            logger.info(f"  Blog Indicators: {js_result['blog_indicators']}")
        else:
            logger.error("✗ JavaScript rendering: FAILED")
            logger.error(f"  Error: {js_result['error']}")
            return False
        return True
    
    js_success = asyncio.run(run_js_test())
    if not js_success:
        return
    
    # Blog structure discovery
    logger.info("=" * 50)
    logger.info("BLOG STRUCTURE DISCOVERY")
    logger.info("=" * 50)
    
    async def run_structure_discovery():
        structure_result = await checker.discover_blog_structure()
        if 'error' not in structure_result:
            logger.info("✓ Blog structure discovery: COMPLETED")
            logger.info(f"  Blog URL: {structure_result.get('blog_url', 'Not found')}")
            logger.info(f"  Posts Found: {len(structure_result.get('post_urls', []))}")
            logger.info(f"  URL Patterns: {structure_result.get('url_patterns', [])}")
            
            # Show first few post URLs as examples
            post_urls = structure_result.get('post_urls', [])
            if post_urls:
                logger.info("  Sample Post URLs:")
                for url in post_urls[:5]:  # Show first 5
                    logger.info(f"    - {url}")
                if len(post_urls) > 5:
                    logger.info(f"    ... and {len(post_urls) - 5} more")
        else:
            logger.error("✗ Blog structure discovery: FAILED")
            logger.error(f"  Error: {structure_result['error']}")
    
    asyncio.run(run_structure_discovery())
    
    logger.info("=" * 50)
    logger.info("CONNECTIVITY TESTS COMPLETE")
    logger.info("=" * 50)


@cli.command()
@click.pass_context
def create_config(ctx):
    """Create a default configuration file."""
    config = ArchiveConfig()
    config_path = Path("archiver_config.json")
    
    if config_path.exists():
        if not click.confirm(f"{config_path} already exists. Overwrite?"):
            click.echo("Configuration creation cancelled.")
            return
    
    ConfigManager.save_config(config, config_path)
    click.echo(f"Configuration file created: {config_path}")
    click.echo("You can edit this file to customize the archiver settings.")


@cli.command()
@click.option('--output', '-o', type=click.Path(), default='output', help='Output directory')
@click.option('--resume/--no-resume', default=True, help='Resume from previous session if available')
@click.option('--state-file', type=click.Path(), help='Custom state file location')
@click.option('--progress-interval', default=30, help='Progress report interval in seconds')
@click.pass_context
def archive(ctx, output, resume, state_file, progress_interval):
    """Archive the blog (full scraping and generation)."""
    import asyncio
    from .archive_orchestrator import ArchiveOrchestrator
    
    config: ArchiveConfig = ctx.obj['config']
    logger = ctx.obj['logger']
    
    logger.info("Starting full archive process...")
    logger.info(f"Target site: {config.site_url}")
    logger.info(f"Output directory: {output}")
    logger.info(f"Resume mode: {'enabled' if resume else 'disabled'}")
    
    output_dir = Path(output)
    state_file_path = Path(state_file) if state_file else None
    
    # Create orchestrator
    orchestrator = ArchiveOrchestrator(config, output_dir, state_file_path)
    
    # Set up progress callback
    def progress_callback(summary):
        click.echo(f"Progress: {summary['completion_rate']:.1f}% "
                  f"({summary['completed_urls']}/{summary['total_urls']}) "
                  f"- Phase: {summary['phase']}")
    
    orchestrator.set_progress_callback(progress_callback)
    
    try:
        # Run the archive process
        result = asyncio.run(orchestrator.archive_full(resume=resume))
        
        if result['success']:
            click.echo("🎉 Archive completed successfully!")
            click.echo(f"Session ID: {result['session_id']}")
            
            summary = result['summary']
            click.echo(f"✅ Successfully archived: {summary['successful_posts']} posts")
            click.echo(f"❌ Failed posts: {summary['failed_posts']}")
            click.echo(f"📊 Success rate: {summary['success_rate']:.1f}%")
            click.echo(f"⏱️  Total time: {summary['total_time']:.1f} seconds")
            click.echo(f"📁 Output location: {summary['output_location']}")
            
            if summary['failed_posts'] > 0:
                click.echo("\n⚠️  Some posts failed to archive. You can retry with:")
                click.echo(f"python -m src.main retry-failed --state-file {output_dir / 'archive_state.json'}")
        
    except KeyboardInterrupt:
        click.echo("\n⏸️  Archive interrupted by user")
        click.echo("📝 Progress has been saved. Resume with:")
        click.echo(f"python -m src.main archive --output {output} --resume")
        
    except Exception as e:
        logger.error(f"Archive failed: {e}")
        click.echo(f"❌ Archive failed: {e}")
        click.echo("📝 Check logs for detailed error information")
        sys.exit(1)


@cli.command()
@click.option('--state-file', type=click.Path(exists=True), help='State file to check')
@click.option('--output', '-o', type=click.Path(), default='output', help='Output directory')
@click.pass_context
def status(ctx, state_file, output):
    """Check the status of an archive session."""
    from .archive_orchestrator import ArchiveOrchestrator
    
    config: ArchiveConfig = ctx.obj['config']
    output_dir = Path(output)
    
    if state_file:
        state_file_path = Path(state_file)
    else:
        state_file_path = output_dir / "archive_state.json"
    
    if not state_file_path.exists():
        click.echo("❌ No archive session found")
        click.echo(f"   Looking for: {state_file_path}")
        return
    
    orchestrator = ArchiveOrchestrator(config, output_dir, state_file_path)
    summary = orchestrator.get_state_summary()
    
    click.echo("📊 Archive Session Status")
    click.echo("=" * 40)
    click.echo(f"Session ID: {summary['session_id']}")
    click.echo(f"Phase: {summary['phase']}")
    click.echo(f"Progress: {summary['completion_rate']:.1f}%")
    click.echo(f"Completed: {summary['completed_urls']}/{summary['total_urls']} URLs")
    click.echo(f"Failed: {summary['failed_urls']} URLs")
    click.echo(f"Elapsed time: {summary['elapsed_time']:.1f} seconds")
    
    if summary['current_url']:
        click.echo(f"Current: {summary['current_url']}")
    
    if summary['estimated_remaining'] > 0:
        click.echo(f"Estimated remaining: {summary['estimated_remaining']:.1f} seconds")


@cli.command()
@click.option('--state-file', type=click.Path(exists=True), help='State file from previous session')
@click.option('--output', '-o', type=click.Path(), default='output', help='Output directory')
@click.pass_context
def retry_failed(ctx, state_file, output):
    """Retry failed URLs from a previous archive session."""
    import asyncio
    from .archive_orchestrator import ArchiveOrchestrator
    
    config: ArchiveConfig = ctx.obj['config']
    logger = ctx.obj['logger']
    output_dir = Path(output)
    
    if state_file:
        state_file_path = Path(state_file)
    else:
        state_file_path = output_dir / "archive_state.json"
    
    if not state_file_path.exists():
        click.echo("❌ No archive session found")
        return
    
    orchestrator = ArchiveOrchestrator(config, output_dir, state_file_path)
    
    try:
        result = asyncio.run(orchestrator.cleanup_failed_urls())
        
        if 'message' in result:
            click.echo(result['message'])
        else:
            click.echo(f"✅ Retried {result['retried_urls']} failed URLs")
            click.echo(f"✅ Successfully recovered: {result['successful_retries']} URLs")
            
            failed_again = result['retried_urls'] - result['successful_retries']
            if failed_again > 0:
                click.echo(f"❌ Still failing: {failed_again} URLs")
    
    except Exception as e:
        logger.error(f"Retry failed: {e}")
        click.echo(f"❌ Retry failed: {e}")


@cli.command()
@click.option('--output', '-o', type=click.Path(), default='output', help='Output directory')
@click.option('--since', help='Only check posts modified since date (YYYY-MM-DD)')
@click.pass_context
def incremental(ctx, output, since):
    """Perform incremental update to detect new or changed posts."""
    import asyncio
    from .incremental_updater import IncrementalUpdater
    
    config: ArchiveConfig = ctx.obj['config']
    logger = ctx.obj['logger']
    
    logger.info("Starting incremental update...")
    
    output_dir = Path(output)
    
    try:
        updater = IncrementalUpdater(config, output_dir)
        result = asyncio.run(updater.check_for_updates(since_date=since))
        
        if result['new_posts'] or result['changed_posts']:
            click.echo(f"📄 Found {result['new_posts']} new posts")
            click.echo(f"🔄 Found {result['changed_posts']} changed posts")
            
            if click.confirm("Do you want to update the archive?"):
                update_result = asyncio.run(updater.update_archive())
                click.echo(f"✅ Archive updated: {update_result['updated_posts']} posts")
        else:
            click.echo("✅ Archive is up to date")
            
    except Exception as e:
        logger.error(f"Incremental update failed: {e}")
        click.echo(f"❌ Incremental update failed: {e}")


if __name__ == '__main__':
    cli()