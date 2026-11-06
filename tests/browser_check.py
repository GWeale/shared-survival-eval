"""Optional isolated headless-Chrome interaction and responsive-layout check.

Run from the repository root: python3 -m tests.browser_check --chrome /path/to/chrome --out /tmp/station-ui
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from shared_survival_eval.agents import Baseline
from shared_survival_eval.replay import render_replay
from shared_survival_eval.runner import run_episode


SCRIPT = r"""
<script>
try {
const check=(condition,message)=>{if(!condition)throw new Error(message)};
check(document.documentElement.dataset.ready==='true','viewer initialized');
check(document.documentElement.scrollWidth<=innerWidth,'initial horizontal overflow');
document.getElementById('next').click();
check(document.documentElement.dataset.frame==='1','next advances');
const selector=document.getElementById('view');
selector.value='0';selector.dispatchEvent(new Event('change'));
check(!document.getElementById('messages').textContent.includes('secret-for-seat-two'),'private message leaked to seat zero');
check(document.getElementById('seats').textContent.includes('Private objectives hidden'),'private objectives filtered');
selector.value='2';selector.dispatchEvent(new Event('change'));
check(document.getElementById('messages').textContent.includes('secret-for-seat-two'),'recipient sees private message');
check(!window.injected,'untrusted text executed');
document.getElementById('prev').click();
check(document.documentElement.dataset.frame==='0','previous returns');
const moments=document.getElementById('frame');
moments.value=String(moments.options.length-1);moments.dispatchEvent(new Event('change'));
check(document.getElementById('actions').textContent.includes('Your reward:'),'terminal reward renders');
check(document.getElementById('next').disabled,'terminal next disabled');
moments.focus();check(document.activeElement===moments,'native selector focus');
check(document.documentElement.scrollWidth<=innerWidth,'terminal horizontal overflow');
moments.value='3';moments.dispatchEvent(new Event('change'));
selector.value='all';selector.dispatchEvent(new Event('change'));
const log=document.getElementById('messages').textContent;
check(log.indexOf('secret-for-seat-two')<log.indexOf('R2'), 'omniscient event chronology');
check(document.documentElement.scrollWidth<=innerWidth,'final horizontal overflow');
document.documentElement.dataset.viewport=String(innerWidth);
document.documentElement.dataset.qa='passed';
} catch(error) {document.documentElement.dataset.qa='failed';document.documentElement.dataset.qaError=error.message;}
</script>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    class TalkingBaseline(Baseline):
        def respond(self, obs, phase):
            reply = super().respond(obs, phase)
            if phase == "discuss" and obs["seat"] == 1:
                reply.decision["private"] = {"to": 2, "text": "secret-for-seat-two"}
                reply.decision["say"] = "<script>window.injected=true</script>"
            return reply
    plan = {"agents": {"fixture": {"type": "baseline", "name": "cooperative"}}, "crews": {"fixture": ["fixture"] * 4}}
    with patch("shared_survival_eval.runner.make_agent", side_effect=lambda c, s: TalkingBaseline("cooperative", s)):
        record = run_episode(plan, "fixture", "shared", 0)
    html = args.out / "fixture.html"
    render_replay(record, html)
    html.write_text(html.read_text().replace("</body>", SCRIPT + "</body>"))
    for name, width, height in [("desktop", 1200, 1100), ("narrow", 500, 1100)]:
        with tempfile.TemporaryDirectory(prefix="station-browser-") as profile:
            result = subprocess.run([args.chrome, "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", "--disable-component-update", f"--user-data-dir={profile}",
                "--dump-dom", f"--screenshot={args.out.resolve() / (name + '.png')}", f"--window-size={width},{height}",
                "--virtual-time-budget=1500", html.resolve().as_uri()], capture_output=True, text=True, timeout=30)
            (args.out / (name + ".dom.html")).write_text(result.stdout)
            if result.returncode or 'data-qa="passed"' not in result.stdout or f'data-viewport="{width}"' not in result.stdout:
                raise RuntimeError(f"{name} browser check failed (exit {result.returncode}); inspect saved DOM")
            print(json.dumps({"viewport": name, "width": width, "checks": "passed", "screenshot": str(args.out / (name + '.png'))}))


if __name__ == "__main__":
    main()
