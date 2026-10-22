import { execFileSync } from "node:child_process";
import type { DockerRequest, DockerResult } from "../shared.ts";
interface Configuration { worker: string; host: string; proof: string; certPath: string; tlsVerify: string; }

/** @deadlineMs 10000 */
export function list(request: DockerRequest): DockerResult {
  const config = JSON.parse(new TextDecoder().decode(request.configuration)) as Configuration;
  const output = execFileSync(config.worker, [config.host, config.proof, config.certPath, config.tlsVerify], { encoding: "utf8", timeout: 10000, maxBuffer: 524288 });
  const firstLine = output.indexOf("\n");
  return { output: new TextEncoder().encode(output.slice(firstLine + 1)) };
}
