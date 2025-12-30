import click
import requests
from md_scraper.scraper import Scraper

@click.group()
def cli():
    pass

@cli.command()
@click.argument('url')
@click.option('--output', '-o', type=click.Path(), help='File path to save the Markdown output.')
@click.option('--dynamic', '-d', is_flag=True, default=False, help='Enable Playwright-based dynamic scraping.')
@click.option('--strip', '-s', multiple=True, help='Tags to strip from the output (can be used multiple times).')
@click.option('--svg-action', type=click.Choice(['image', 'preserve', 'strip']), default='image', help='Action for inline <svg> tags (default: image).')
@click.option('--server', help='Remote scraper server URL (e.g., https://my-scraper.run.app). If set, scraping happens remotely.')
def scrape(url, output, dynamic, strip, svg_action, server):
    """Scrape a URL and print the Markdown content."""
    
    markdown = None
    
    if server:
        # Remote scraping mode
        api_url = f"{server.rstrip('/')}/api/scrape"
        payload = {
            'url': url,
            'dynamic': dynamic,
            'svg_action': svg_action,
            'strip_tags': list(strip) if strip else []
        }
        try:
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            markdown = result.get('markdown', '')
        except requests.exceptions.RequestException as e:
            click.echo(f"Error communicating with remote server: {e}", err=True)
            if hasattr(e, 'response') and e.response is not None:
                 click.echo(f"Server response: {e.response.text}", err=True)
            raise click.Abort()
    else:
        # Local scraping mode
        scraper = Scraper()
        try:
            # Pass options to scrape method
            scrape_options = {'svg_action': svg_action}
            if strip:
                scrape_options['strip'] = list(strip)
                
            result = scraper.scrape(url, dynamic=dynamic, **scrape_options)
            markdown = result['markdown']
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort()

    if output:
        with open(output, 'w') as f:
            f.write(markdown)
        click.echo(f"Successfully scraped {url} to {output}")
    else:
        click.echo(markdown)

@cli.command()
def hello():
    click.echo("Hello from md-scraper!")

if __name__ == "__main__":
    cli()
