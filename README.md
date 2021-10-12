# Auto Sync Repos Action

Sync all commits from one repo to another automatically by creating pull request.


## Usage

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
