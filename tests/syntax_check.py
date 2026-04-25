import sys

def check_syntax(filepath):
    print(f"Checking syntax for {filepath}...")
    with open(filepath, 'r') as f:
        content = f.read()

    try:
        compile(content, filepath, 'exec')
        print(f"  Syntax check PASSED for {filepath}")
    except SyntaxError as e:
        print(f"  Syntax check FAILED for {filepath}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  An error occurred while checking {filepath}: {e}")
        # Not a syntax error, but maybe something else (e.g. file not found)
        sys.exit(1)

if __name__ == "__main__":
    check_syntax('src/md_scraper/web/app.py')
    check_syntax('src/md_scraper/cli.py')
