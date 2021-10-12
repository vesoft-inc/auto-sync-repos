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
    - uses: vesoft-inc/auto-sync-repos@master
      with:
        gh-pat: ${{ secrets.GH_PAT }}
        username: bot-name
        email: bot-name-example@vesoft.com
        source-repo: vesoft-inc/nebula
        target-repo: ${{ github.repository }}
        dingtalk-access-token: ${{ secrets.DING_ACCESS_TOKEN }}
        dingtalk-secret: ${{ secrets.DING_SECRET }}
```
