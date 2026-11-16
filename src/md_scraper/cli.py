import click
import requests
import os
import re
import time
from md_scraper.scraper import Scraper
from md_scraper.ts_engine import scrape_ts
from md_scraper.utils import sanitize_filename, get_title_from_result, select_output
from md_scraper.crawler import Crawler

def process_url_logic(url, server, dynamic, strip, svg_action, image_action, assets_dir, proxy=None, user_agent=None, delay=0.0, retries=3, scraper=None, output_format='markdown', engine='python'):
    """Helper to process a single URL (local or remote). Returns result dict."""
    if server:
        # Remote scraping mode
        api_url = f"{server.rstrip('/')}/api/scrape"
        payload = {
            'url': url,
            'dynamic': dynamic,
            'svg_action': svg_action,
            'image_action': image_action,
            'strip_tags': list(strip) if strip else [],
            'proxy': proxy,
            'user_agent': user_agent,
            'delay': delay,
            'retries': retries,
            'format': output_format,
            'engine': engine,
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
        if engine == 'ts':
            # Run the TypeScript engine via its --json CLI mode; the
            # result shape is identical to the Python engine's, so the
            # caller's output handling works unchanged.
            return scrape_ts(
                url,
                dynamic=dynamic,
                svg_action=svg_action,
                image_action=image_action,
                assets_dir=assets_dir,
                strip_tags=list(strip) if strip else [],
                proxy=proxy,
                user_agent=user_agent,
                delay=delay,
                retries=retries,
            )
        scrape_options = {
            'svg_action': svg_action,
            'image_action': image_action,
            'assets_dir': assets_dir,
            'base_url': url,
            'proxy': proxy,
            'user_agent': user_agent,
            'delay': delay,
            'retries': retries
        }
        if strip:
            scrape_options['strip'] = list(strip)

        if scraper:
            return scraper.scrape(url, dynamic=dynamic, **scrape_options)
        else:
            try:
                scraper_cm = Scraper(proxy=proxy, user_agent=user_agent, delay=delay, retries=retries)
            except TypeError:
                scraper_cm = Scraper()
            with scraper_cm as temp_scraper:
                return temp_scraper.scrape(url, dynamic=dynamic, **scrape_options)

# Banner modes for the global --banner option (see cli() below).
BANNER_MODES = ('default', 'stdout', 'stderr', 'none')


def _banner_target(banner_mode, output_format):
    """Decide where the '--- URL: ---' banner goes: 'stdout', 'stderr' or None.

    default: current behavior — on stdout, except suppressed for the two
        full-document formats (html-document, html-raw) so their output
        starts with the DOCTYPE instead of a plain-text banner.
    stdout: always on stdout, even for the document formats.
    stderr: always on stderr, keeping stdout clean for every format.
    none: never printed.
    """
    if banner_mode == 'none':
        return None
    if banner_mode == 'stdout':
        return 'stdout'
    if banner_mode == 'stderr':
        return 'stderr'
    # default
    if output_format in ('html-document', 'html-raw'):
        return None
    return 'stdout'


@click.group()
@click.option('--banner', type=click.Choice(BANNER_MODES), default='default', show_default=True,
              help='Where to print the "--- URL: ---" banner: default (current behavior — on stdout, except suppressed for html-document and html-raw so the output starts with the DOCTYPE), stdout (always on stdout), stderr (always on stderr, keeping stdout clean), or none (never printed).')
@click.pass_context
def cli(ctx, banner):
    # Global option: stored on the context for subcommands to read.
    ctx.obj = {'banner': banner}

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
@click.option('--proxy', help='Proxy server URL (e.g., http://proxy:8080, socks5://127.0.0.1:1080).')
@click.option('--user-agent', '-ua', help='Custom User-Agent header or "random" for rotating User-Agents.')
@click.option('--delay', type=float, default=0.0, help='Delay in seconds between requests (default: 0.0).')
@click.option('--retries', type=int, default=3, help='Max retry attempts on request failure (default: 3).')
@click.option('--format', 'output_format', type=click.Choice(['markdown', 'html', 'html-document', 'html-raw']), default='markdown', show_default=True, help='Output format: markdown (default), html (cleaned main content as HTML, content-equivalent of the Markdown), html-document (that content wrapped in a complete standalone HTML document, ready to open in a browser), or html-raw (full fetched HTML document).')
@click.option('--engine', type=click.Choice(['python', 'ts']), default='python', show_default=True, help='Scraper engine: python (default) or ts (TypeScript engine in typescript/, run via its --json CLI mode). With --server, the engine choice is sent to the server.')
@click.pass_context
def scrape(ctx, urls, output, dynamic, strip, svg_action, image_action, assets_dir, server, crawl, depth, max_pages, only_subpaths, proxy, user_agent, delay, retries, output_format, engine):
    """Scrape URL(s) and print/save content in the requested format.

    URLS can be web links or a path to a text file containing URLs.

    The '--- URL: ---' banner printed before each result is controlled by
    the global --banner option (see `scraper --help`): it goes before the
    subcommand, e.g. `scraper --banner stderr scrape URL`.
    """
    # Banner placement for this run, from the global --banner option.
    banner_mode = (ctx.obj or {}).get('banner', 'default')
    banner_target = _banner_target(banner_mode, output_format)
    
    initial_target_urls = []
    
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
    
    try:
        # We use a context manager to reuse the Scraper instance across multiple URLs if local
        from contextlib import nullcontext
        if server or engine == 'ts':
            # No Python Scraper needed: remote mode, or the TS engine
            # (process_url_logic shells out to it per URL).
            scraper_cm = nullcontext()
        else:
            try:
                scraper_cm = Scraper(proxy=proxy, user_agent=user_agent, delay=delay, retries=retries)
            except TypeError:
                scraper_cm = Scraper()
        
        with scraper_cm as scraper:
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

                    result = process_url_logic(
                        current_url, server, dynamic, strip, svg_action, image_action, current_assets_dir,
                        proxy=proxy, user_agent=user_agent, delay=delay, retries=retries, scraper=scraper,
                        output_format=output_format, engine=engine
                    )
                    content, extension = select_output(result, output_format, scraper)

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
                            filename = f"{sanitize_filename(title)}{extension}"
                            file_path = os.path.join(output, filename)

                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        click.echo(f"  -> Saved: {file_path}")
                    else:
                        # Print to stdout. The banner goes where the global
                        # --banner option says: with the default it is
                        # omitted for the full-document formats so the
                        # output starts with the DOCTYPE (a banner before
                        # it would put the browser in quirks mode).
                        if banner_target == 'stdout':
                            click.echo(f"\n--- URL: {current_url} ---\n")
                        elif banner_target == 'stderr':
                            click.echo(f"\n--- URL: {current_url} ---\n", err=True)
                        click.echo(content)
                    
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
                                 # Reuse existing scraper if available
                                 if scraper:
                                     links = scraper.extract_links(raw_html, current_url)
                                 else:
                                     with Scraper() as temp_scraper:
                                         links = temp_scraper.extract_links(raw_html, current_url)
                            else:
                                 links = result.get('nav_links', [])

                        iterator.add_links(links, current_depth)
                                
                except Exception as e:
                    click.echo(f"  -> Failed to scrape {current_url}: {e}", err=True)
                    # Don't abort batch on single failure, unless it's a single requested URL (non-crawl)
                    if not crawl and count == 1:
                            raise click.Abort()
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        raise click.Abort()

@cli.command()
def hello():
    click.echo("Hello from md-scraper!")

if __name__ == "__main__":
    cli()
