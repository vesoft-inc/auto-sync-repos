# Auto Sync Repos Action

Sync all commits from one public repo to another private repo by creating pull request automatically.

## Inputs

### `from_repo`

**Required** The repository need to sync.

### `repo_token`

**Required** The repository token to access the codebase.

### `dingtalk_access_token`

**Required** The access token of dingtalk. Default `""`.

### `dingtalk_secret`

**Required** The secret of dingtalk. Default `""`.

## Usage

In private repository workflow:

```yaml
name: My Workflow
on:
  schedule:
    - cron: '0 8 * * *'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: vesoft-inc/auto-sync-repos@master
      with:
        from_repo: vesoft-inc/nebula
        repo_token: ${{ secrets.GITHUB_TOKEN }}
        dingtalk_access_token: ${{ secrets.DING_ACCESS_TOKEN }}
        dingtalk_secret: ${{ secrets.DING_SECRET }}
```
