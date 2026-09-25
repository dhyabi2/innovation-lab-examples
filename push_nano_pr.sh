#!/usr/bin/env bash
# Push the Nano payment example to the fetchai fork and open a PR.
# Run from ~/work/fetchai-il after the GitHub rate limit resets.
set -euo pipefail
cd /root/work/fetchai-il

# Read the dhyabi2 token from gh hosts (never print).
TOKEN=$(grep -o 'ghp_[A-Za-z0-9]*' /root/.config/gh/hosts.yml | head -1)
UP=fetchai/innovation-lab-examples
BR=feat/nano-xno-payment-agent
FORK=dhyabi2/innovation-lab-examples

echo "1. star the repo (CONTRIBUTING requires it)"
curl -s -o /dev/null -w "star:%{http_code}\n" -X PUT -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/user/starred/$UP"

echo "2. create fork"
curl -s -o /tmp/fork.json -w "fork:%{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/$UP/forks"
python3 -c "import json;d=json.load(open('/tmp/fork.json'));print('fork full_name:',d.get('full_name'),'| msg:',d.get('message'))"

# wait for fork to be ready
sleep 8

echo "3. push branch to fork (token-in-URL, scrubbed after)"
git remote remove fork 2>/dev/null || true
git remote add fork "https://dhyabi2:${TOKEN}@github.com/${FORK}.git"
git push fork "$BR" 2>&1 | tail -3
# scrub the token immediately
git remote set-url fork "https://github.com/${FORK}.git"

echo "4. verify remote branch sha"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/$FORK/git/refs/heads/$BR" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('remote sha:',d.get('object',{}).get('sha'))"
LOCAL=$(git rev-parse HEAD)
echo "local  sha: $LOCAL"

echo "5. open PR"
python3 -c "
import json
body=open('/root/work/fetchai-il/pr_body_nano.md').read()
print(json.dumps({'title':'feat: Nano (XNO) settlement rail for the payment protocol (seller example)','head':'$BR','base':'main','body':body}))
" > /tmp/pr_payload.json
curl -s -o /tmp/pr_out.json -w "pr:%{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d @/tmp/pr_payload.json "https://api.github.com/repos/$UP/pulls"
python3 -c "import json;d=json.load(open('/tmp/pr_out.json'));print('PR url:',d.get('html_url'));print('number:',d.get('number'));print('msg:',d.get('message'))"
