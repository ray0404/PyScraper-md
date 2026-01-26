import click
import requests
import os
import re
import time
from md_scraper.scraper import Scraper
from md_scraper.utils import sanitize_filename, get_title_from_result
from md_scraper.crawler import Crawler

def process_url_logic(url, server, dynamic, strip, svg_action, image_action, assets_dir):
    """Helper to process a single URL (local or remote). Returns result dict."""
    if server:
        # Remote scraping mode
        api_url = f"{server.rstrip('/')}/api/scrape"
        payload = {
            'url': url,
            'dynamic': dynamic,
            'svg_action': svg_action,
            'image_action': image_action,
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
        scrape_options = {
            'svg_action': svg_action,
            'image_action': image_action,
            'assets_dir': assets_dir,
            'base_url': url
        }
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
@click.option('--svg-action', type=click.Choice(['image', 'preserve', 'strip', 'file']), default='image', help='Action for inline <svg> tags (default: image).')
@click.option('--image-action', type=click.Choice(['remote', 'base64', 'file']), default='remote', help='Action for <img> tags (default: remote).')
@click.option('--assets-dir', help='Directory to save images if using "file" action.')
@click.option('--server', help='Remote scraper server URL (e.g., https://my-scraper.run.app). If set, scraping happens remotely.')
@click.option('--crawl', '-c', is_flag=True, default=False, help='Recursively crawl links found on the page.')
@click.option('--depth', type=int, default=3, help='Crawling depth (default: 3).')
@click.option('--max-pages', type=int, default=10, help='Maximum number of pages to crawl per initial URL (default: 10).')
@click.option('--only-subpaths', is_flag=True, default=False, help='Restrict crawling to subpaths of the initial URL(s).')
def scrape(urls, output, dynamic, strip, svg_action, image_action, assets_dir, server, crawl, depth, max_pages, only_subpaths):
    """Scrape URL(s) and print/save Markdown.
    
    URLS can be web links or a path to a text file containing URLs.
    """
    
    initial_target_urls = []
    
    # ... (existing parsing code) ...
    for u in urls:
        if os.path.isfile(u):
            # Check extension to decide if it's a target file or a list of URLs
            ext = os.path.splitext(u)[1].lower()
            if ext in ['.html', '.htm', '.mht', '.mhtml']:
                initial_target_urls.append(u)
            else:
                try:
                    with open(u, 'r') as f:
                        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                        initial_target_urls.extend(lines)
                except Exception as e:
                    click.echo(f"Error reading file {u}: {e}", err=True)
        else:
            initial_target_urls.append(u)
            
    if not initial_target_urls:
        click.echo("No URLs provided.", err=True)
        return

    # Check output directory constraint early
    count = len(initial_target_urls)
    # If crawling is enabled, we will definitely have multiple files, so enforce directory output if output is specified
    if output and (count > 1 or crawl):
         if os.path.exists(output) and os.path.isfile(output):
             click.echo(f"Error: Output '{output}' is a file. When crawling or scraping multiple URLs, please specify a directory.", err=True)
             raise click.Abort()
         if not os.path.exists(output):
             os.makedirs(output)

    # 3. Process Loop
    if crawl:
        iterator = Crawler(initial_target_urls, max_depth=depth, max_pages=max_pages, only_subpaths=only_subpaths)
    else:
        # Simple iterator for non-crawl mode
        iterator = zip(initial_target_urls, [0]*len(initial_target_urls))

    processed_count = 0
    
    for current_url, current_depth in iterator:
        processed_count += 1
        prefix = f"[{processed_count}]" 
        if crawl:
            prefix += f" (Depth {current_depth})"
        
        click.echo(f"{prefix} Scraping {current_url}...", err=True)

        try:
            # Handle automatic assets directory if using 'file' action
            current_assets_dir = assets_dir
            if (svg_action == 'file' or image_action == 'file') and not current_assets_dir:
                if output:
                    base_path = output if os.path.isdir(output) else os.path.dirname(output)
                    current_assets_dir = os.path.join(base_path or '.', 'assets')
                else:
                    current_assets_dir = 'assets'

            result = process_url_logic(current_url, server, dynamic, strip, svg_action, image_action, current_assets_dir)
            markdown = result.get('markdown', '')
            
            # Determine Output
            if output:
                # Save to directory with auto-name
                if not crawl and count == 1 and not os.path.isdir(output) and not output.endswith('/'):
                        # Single file case
                        file_path = output
                else:
                    # Directory case
                    title = get_title_from_result(result, current_url)
                    # Sanitize more aggressively for filenames
                    filename = f"{sanitize_filename(title)}.md"
                    file_path = os.path.join(output, filename)
                
                with open(file_path, 'w') as f:
                    f.write(markdown)
                click.echo(f"  -> Saved: {file_path}")
            else:
                # Print to stdout
                click.echo(f"\n--- URL: {current_url} ---\n")
                click.echo(markdown)
            
            # Feed Crawler
            if crawl and isinstance(iterator, Crawler):
                # Try to get all internal links first
                links = result.get('internal_links')
                
                # Fallback: if 'internal_links' is missing (e.g. older server version), 
                # or empty, try 'nav_links' or manual extraction
                if links is None:
                    # Fallback extraction from raw_html
                    raw_html = result.get('raw_html', '')
                    if raw_html:
                         # We instantiate a local Scraper just for link extraction
                         temp_scraper = Scraper()
                         links = temp_scraper.extract_links(raw_html, current_url)
                    else:
                         links = result.get('nav_links', [])

                iterator.add_links(links, current_depth)
                        
        except Exception as e:
            click.echo(f"  -> Failed to scrape {current_url}: {e}", err=True)
            # Don't abort batch on single failure, unless it's a single requested URL (non-crawl)
            if not crawl and count == 1:
                    raise click.Abort()

@cli.command()
def hello():
    click.echo("Hello from md-scraper!")

if __name__ == "__main__":
    cli()
