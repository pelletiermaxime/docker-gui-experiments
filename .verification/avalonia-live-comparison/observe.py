"""Record native startup, search and Refresh through an owned desktop window."""
from pathlib import Path
import csv
import fcntl
import io
import json
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
binary = ROOT / 'experiments/live-docker/avalonia-containers/build/self-contained/AvaloniaContainers'
environment = dict(os.environ, GDK_BACKEND='x11', DOCKER_HOST='unix:///var/run/docker.sock', AVALONIA_GLOBAL_SCALE_FACTOR='1')
environment.pop('WAYLAND_DISPLAY', None)
lock = open(f'/tmp/ferrydock-native-verification-{os.getuid()}.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
record = {'query': 'hexfit-activepieces', 'actions': []}


def command(*args):
    return subprocess.check_output(args, env=environment, text=True, timeout=15)


def capture(name):
    image = OUT / f'{name}.png'
    command('magick', 'import', '-window', window, str(image))
    text = command('tesseract', str(image), 'stdout', '--psm', '6')
    (OUT / f'{name}.txt').write_text(text)
    return image, text


def click_word(image, word):
    tsv = command('tesseract', str(image), 'stdout', '--psm', '11', 'tsv')
    matches = [r for r in csv.DictReader(io.StringIO(tsv), delimiter='\t')
               if word.lower() in r['text'].lower()]
    if len(matches) != 1:
        raise RuntimeError(f'Cannot uniquely locate {word} in the captured owned window')
    row = matches[0]
    x = int(row['left']) + int(row['width']) // 2
    y = int(row['top']) + int(row['height']) // 2
    command('xdotool', 'windowactivate', '--sync', window)
    command('xdotool', 'mousemove', '--window', window, str(x), str(y))
    command('xdotool', 'click', '1')
    record['actions'].append({'click': word, 'client_point': [x, y]})


with (OUT / 'native.log').open('w') as log:
    process = subprocess.Popen([str(binary)], cwd=ROOT, env=environment,
                               stdout=log, stderr=log, start_new_session=True)
    try:
        deadline = time.monotonic() + 20
        window = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('App exited before observation')
            query = subprocess.run(['xdotool', 'search', '--all', '--onlyvisible', '--pid', str(process.pid)],
                                   env=environment, capture_output=True, text=True)
            if query.returncode == 0:
                window = query.stdout.splitlines()[0]
                break
            time.sleep(.2)
        if window is None:
            raise RuntimeError('No owned window found')
        command('xdotool', 'windowactivate', '--sync', window)
        command('xdotool', 'windowsize', '--sync', window, '1000', '680')
        time.sleep(2)
        before, record['before_text'] = capture('native-before')
        command('xdotool', 'windowfocus', '--sync', window)
        record['keyboard_focus'] = command('xdotool', 'getwindowfocus').strip()
        record['actions'].append({'keyboard_target': 'Initially focused Entry; native focus restored immediately before input'})
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a')
        command('xdotool', 'type', '--clearmodifiers', '--delay', '10', record['query'])
        time.sleep(1)
        _, record['search_text'] = capture('native-search')
        command('xdotool', 'windowfocus', '--sync', window)
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a', 'BackSpace')
        time.sleep(.5)
        cleared, record['cleared_text'] = capture('native-cleared')
        before_refresh = (OUT / 'native.log').read_text().count('Docker load:')
        command('xdotool', 'windowfocus', '--sync', window)
        command('xdotool', 'key', '--clearmodifiers', 'Tab', 'space')
        record['actions'].append({'keyboard': 'Tab from Entry to Refresh, then Space'})
        time.sleep(1)
        _, record['refreshed_text'] = capture('native-refreshed')
        record.update(loads_before_refresh=before_refresh,
                      loads_after_refresh=(OUT / 'native.log').read_text().count('Docker load:'),
                      pid=process.pid, window=window)
    except Exception as error:
        record['error'] = str(error)
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        record['owned_process_exited'] = process.poll() is not None
        (OUT / 'native-observation.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: v for k, v in record.items() if not k.endswith('_text')}, indent=2))
