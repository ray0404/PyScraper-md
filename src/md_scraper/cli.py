import click
import requests
import os
import re
import time
from md_scraper.scraper import Scraper

def sanitize_filename(name):
    """Sanitize a string to be safe for filenames."""
    s = str(name).strip().replace(' ', '_')
    s = re.sub(r'(?u)[^-\w.]', '', s)
    return s[:50]

def get_title_from_result(result, url):
    """Extract a title for the file from metadata or URL."""
    meta = result.get('metadata', {})
    title = meta.get('title')
    
    if not title:
        # Fallback to URL parts
        try:
            from urllib.parse import urlparse
            path = urlparse(url).path
            if path and path != '/':
                title = path.strip('/').split('/')[-1]
            else:
                title = urlparse(url).netloc
        except:
            title = 'scraped_page'
            
    if not title:
        title = f'scraped_{int(time.time())}'
        
    return sanitize_filename(title)

def process_url_logic(url, server, dynamic, strip, svg_action):
    """Helper to process a single URL (local or remote). Returns result dict."""
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
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                 raise Exception(f"Server error ({e.response.status_code}): {e.response.text}")
            raise Exception(f"Connection error: {e}")
    else:
        # Local scraping mode
        scraper = Scraper()
        # Pass options to scrape method
        scrape_options = {'svg_action': svg_action}
        if strip:
            scrape_options['strip'] = list(strip)
            
        return scraper.scrape(url, dynamic=dynamic, **scrape_options)

@click.group()
def cli():
    pass

@cli.command()
@click.argument('urls', nargs=-1)
@click.option('--output', '-o', type=click.Path(), help='File path (single URL) or Directory (multiple URLs) to save output.')
@click.option('--dynamic', '-d', is_flag=True, default=False, help='Enable Playwright-based dynamic scraping.')
@click.option('--strip', '-s', multiple=True, help='Tags to strip from the output (can be used multiple times).')
@click.option('--svg-action', type=click.Choice(['image', 'preserve', 'strip']), default='image', help='Action for inline <svg> tags (default: image).')
@click.option('--server', help='Remote scraper server URL (e.g., https://my-scraper.run.app). If set, scraping happens remotely.')
def scrape(urls, output, dynamic, strip, svg_action, server):
    """Scrape URL(s) and print/save Markdown.
    
    URLS can be web links or a path to a text file containing URLs.
    """
    
    target_urls = []
    
    # 1. Parse Inputs (URLs or Files)
    for u in urls:
        if os.path.isfile(u):
            try:
                with open(u, 'r') as f:
                    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                    target_urls.extend(lines)
            except Exception as e:
                click.echo(f"Error reading file {u}: {e}", err=True)
        else:
            target_urls.append(u)
            
    if not target_urls:
        click.echo("No URLs provided.", err=True)
        return

    count = len(target_urls)
    is_batch = count > 1
    
    # 2. Prepare Output Directory if batch mode
    if is_batch and output:
        if not os.path.exists(output):
            os.makedirs(output)
        elif os.path.isfile(output):
             click.echo(f"Error: Output '{output}' is a file, but multiple URLs were provided. Please specify a directory.", err=True)
             raise click.Abort()

    # 3. Process Loop
    for i, url in enumerate(target_urls):
        prefix = f"[{i+1}/{count}] " if is_batch else ""
        if is_batch:
            click.echo(f"{prefix}Scraping {url}...", err=True)
            
        try:
            result = process_url_logic(url, server, dynamic, strip, svg_action)
            markdown = result.get('markdown', '')
            
            # Determine Output
            if output:
                if is_batch or os.path.isdir(output):
                    # Save to directory with auto-name
                    title = get_title_from_result(result, url)
                    filename = f"{title}.md"
                    file_path = os.path.join(output, filename)
                    
                    with open(file_path, 'w') as f:
                        f.write(markdown)
                    click.echo(f"{prefix}Saved: {file_path}")
                else:
                    # Single URL, explicit file path
                    with open(output, 'w') as f:
                        f.write(markdown)
                    click.echo(f"Successfully scraped {url} to {output}")
            else:
                # Print to stdout
                if is_batch:
                    click.echo(f"\n--- URL: {url} ---\n")
                click.echo(markdown)
                
        except Exception as e:
            click.echo(f"{prefix}Failed to scrape {url}: {e}", err=True)
            # Don't abort batch on single failure
            if not is_batch:
                raise click.Abort()

@cli.command()
def hello():
    click.echo("Hello from md-scraper!")

if __name__ == "__main__":
    cli()
