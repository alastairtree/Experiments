# CI workflow

`not-so-fat-lab.yml` is the GitHub Actions workflow that rebuilds the image
monthly (and on manual dispatch), smoke-tests it, and publishes it to GHCR —
plus a fast Dockerfile lint on pushes/PRs.

## Activate it

GitHub only runs workflows stored under `.github/workflows/`. Copy this file
there and commit it:

```bash
mkdir -p .github/workflows
cp not-so-fat-lab/ci/not-so-fat-lab.yml .github/workflows/not-so-fat-lab.yml
git add .github/workflows/not-so-fat-lab.yml
git commit -m "Activate not-so-fat-lab CI workflow"
git push
```

It is shipped here rather than pre-installed under `.github/workflows/` because
the session that generated it used a git token without the `workflow` OAuth
scope, which GitHub requires to push workflow files. Adding it yourself (via a
normal `git push` with the `workflow` scope, or straight through the GitHub web
UI) takes one commit.

No secrets are required for the build. Optionally add an `MLM_LICENSE_FILE`
repository secret (pointing at a licence server reachable from the runner) to
enable the extra `matlab -batch` smoke test.
