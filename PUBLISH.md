# Publishing the Classics Library site

The site is generated into this folder by `build.py` and is meant to be served by
GitHub Pages at **https://luchuz.github.io/classics/** (every canonical URL, sitemap
entry and the links in the YouTube video descriptions already point there).

Nothing has been pushed yet. To publish, run these two commands once:

```bash
cd ~/classics-site
gh repo create luchuz/classics --public --source=. --push
gh api repos/luchuz/classics/pages -X POST -f 'source[branch]=main' -f 'source[path]=/'
```

Pages takes a minute or two to go live the first time. After that, each bot's `run.sh`
calls `deploy.sh` after a successful post, which rebuilds the site, commits, and pushes.

Manual rebuild + push any time: `~/classics-site/deploy.sh` (log in `deploy.log`).
