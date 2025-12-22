import click
from md_scraper.scraper import Scraper

@click.group()
def cli():
    pass

@cli.command()
@click.argument('url')
def scrape(url):
    """Scrape a URL and print the Markdown content."""
    scraper = Scraper()
    try:
        result = scraper.scrape(url)
        click.echo(result['markdown'])
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@cli.command()
def hello():
    click.echo("Hello from md-scraper!")

if __name__ == "__main__":
    cli()
