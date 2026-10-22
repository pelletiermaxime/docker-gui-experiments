import Docker from 'dockerode';
import os from 'node:os';
import fs from 'node:fs';

// The SDK owns Docker HTTP, API negotiation and response decoding. The pipe
// carries bounded display fields only; it is not a Docker implementation.
const endpoint = process.env.DOCKER_HOST;
const options = { timeout: 10000 };
if (endpoint?.startsWith('unix://')) options.socketPath = endpoint.slice(7);
else if (endpoint?.startsWith('npipe://')) options.socketPath = endpoint.slice(8);
else if (endpoint) {
  const url = new URL(endpoint.replace(/^tcp:/, 'http:'));
  options.host = url.hostname;
  options.port = Number(url.port || (url.protocol === 'https:' ? 2376 : 2375));
  options.protocol = process.env.DOCKER_TLS_VERIFY === '1' ? 'https' : url.protocol.slice(0, -1);
} else options.socketPath = os.platform() === 'win32' ? '//./pipe/docker_engine' : '/var/run/docker.sock';
if (process.env.DOCKER_CERT_PATH) {
  for (const [key, name] of [['ca', 'ca.pem'], ['cert', 'cert.pem'], ['key', 'key.pem']])
    options[key] = fs.readFileSync(`${process.env.DOCKER_CERT_PATH}/${name}`);
}
const deadline = setTimeout(() => { console.log('Docker request exceeded 10 seconds'); process.exit(1); }, 10000);
try {
  const started = performance.now();
  const docker = new Docker(options);
  const info = await docker.version();
  docker.modem.version = `v${info.ApiVersion}`;
  const containers = await docker.listContainers({ all: true });
  if (containers.length > 20000) throw new Error('Container limit exceeded (20,000)');
  const elapsed = performance.now() - started;
  const clean = value => String(value ?? '').replace(/[\t\r\n]/g, ' ').slice(0, 512);
  const rows = containers.map(c => [c.Id, clean((c.Names?.[0] || c.Id.slice(0, 12)).replace(/^\//, '')), clean(c.Image), clean(c.State), clean(c.Status)]).sort((a, b) => a[1].localeCompare(b[1]));
  const output = [`${containers.length} containers · ${elapsed.toFixed(1)} ms`, ...rows.map(r => r.join('\t'))].join('\n');
  if (Buffer.byteLength(output) > 512 * 1024 - 1) throw new Error('Display response exceeds 512 KiB');
  console.log(output);
  const proof = `Docker load: count=${containers.length} elapsed_ms=${elapsed.toFixed(3)} ids=${containers.map(c => c.Id).sort().join(',')}`;
  console.error(proof);
  if (process.env.NATIVE_DOCKER_PROOF) fs.appendFileSync(process.env.NATIVE_DOCKER_PROOF, proof + '\n');
} catch (error) { console.log(error.message); process.exitCode = 1; }
finally { clearTimeout(deadline); }
