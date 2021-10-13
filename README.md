# Auto Sync Repos Action

Sync all commits from one public repo to another private repo by creating pull request automatically.

## Inputs

### `from-repo`

**Required** The repository need to sync. Default `""`.

### `dingtalk-access-token`

**Required** The access token of dingtalk. Default `""`.

### `dingtalk-secret`

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
        from-repo: vesoft-inc/nebula
        dingtalk-access-token: ${{ secrets.DING_ACCESS_TOKEN }}
        dingtalk-secret: ${{ secrets.DING_SECRET }}
```
