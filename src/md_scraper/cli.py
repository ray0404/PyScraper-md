import click
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
def scrape(url, output, dynamic, strip, svg_action):
    """Scrape a URL and print the Markdown content."""
    scraper = Scraper()
    try:
        # Pass options to scrape method
        # markdownify 'strip' is a list
        scrape_options = {'svg_action': svg_action}
        if strip:
            scrape_options['strip'] = list(strip)
            
        result = scraper.scrape(url, dynamic=dynamic, **scrape_options)
        
        markdown = result['markdown']
        
        if output:
            with open(output, 'w') as f:
                f.write(markdown)
            click.echo(f"Successfully scraped {url} to {output}")
        else:
            click.echo(markdown)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@cli.command()
def hello():
    click.echo("Hello from md-scraper!")

if __name__ == "__main__":
    cli()
