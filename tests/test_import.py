def test_import():
    try:
        import md_scraper
        assert md_scraper
    except ImportError:
        assert False, "md_scraper could not be imported"
