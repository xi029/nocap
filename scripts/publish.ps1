# Rename the existing GitHub repository to NoCap and refresh its metadata.
# GitHub keeps redirects from the old name, so existing clones and links keep working.
param(
    [string]$Old = 'xi029/jev-lens',
    [string]$New = 'nocap'
)
# Native commands report failure through $LASTEXITCODE, checked after each step.
$ErrorActionPreference = 'Continue'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'Install GitHub CLI from https://cli.github.com, then run gh auth login and this script again.'
}
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Run gh auth login first.' }
$taskDirty = git status --porcelain
if ($taskDirty) { throw 'Commit your intended files before publishing.' }

$owner = $Old.Split('/')[0]
gh repo view "$owner/$New" --json name --jq .name 2>$null
if ($LASTEXITCODE -ne 0) {
    gh repo rename $New --repo $Old --yes
    if ($LASTEXITCODE -ne 0) { throw 'Rename failed. Inspect GitHub before retrying.' }
}
git remote set-url origin "https://github.com/$owner/$New.git"
git push origin HEAD
gh repo edit "$owner/$New" `
    --description 'No evidence, no answer. 🧢 The hallucination firewall for RAG & AI agents: MCP server, Python SDK, OpenAI-compatible / Ollama judges, CI route tests.' `
    --homepage "https://github.com/$owner/$New#readme"
gh api -X PUT "repos/$owner/$New/topics" `
    -f 'names[]=rag' -f 'names[]=hallucination' -f 'names[]=llm' -f 'names[]=mcp' `
    -f 'names[]=mcp-server' -f 'names[]=ai-agents' -f 'names[]=guardrails' -f 'names[]=ollama' `
    -f 'names[]=openai' -f 'names[]=deepseek' -f 'names[]=langchain' -f 'names[]=llamaindex' `
    -f 'names[]=claude-code' -f 'names[]=local-first' -f 'names[]=python' -f 'names[]=evaluation'
if ($LASTEXITCODE -ne 0) { Write-Warning 'Repository updated, but topics were not.' }
Write-Output "Published https://github.com/$owner/$New"
