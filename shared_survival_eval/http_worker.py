"""Single HTTP request child; parent enforces the overall wall-clock deadline."""
import http.client
import json
import sys
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):return None


def main():
    try:
        value=json.load(sys.stdin)
        request=urllib.request.Request(value['endpoint'],data=json.dumps(value['body']).encode(),headers=value['headers'])
        with urllib.request.build_opener(NoRedirect).open(request,timeout=value['timeout']) as response:
            body=response.read(1_000_001)
        if len(body)>1_000_000:raise ValueError('response too large')
        sys.stdout.buffer.write(body)
    except (http.client.HTTPException,urllib.error.URLError,TimeoutError,ValueError,KeyError,TypeError,OSError):
        print('HTTP transport failed; details omitted',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
