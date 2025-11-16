## Overview
Enable Good Agent instances to converse with agents running in other environments through an OpenAI-chat-compatible transport while preserving async, Python-first ergonomics, and composability with existing multi-agent primitives.

## Requirements & Constraints
1. Maintain async-first API (context manager lifecycle, `call/execute`, message history slicing).
2. Support any remote agent reachable via OpenAI-compatible HTTPS API; future-proof for A2A/websocket transports.
3. Integrate with existing multi-agent piping (`researcher | writer`), tool invocation flow, telemetry, and stateful resources.
4. Respect security boundaries (API keys, sandboxing), provide retry/backoff hooks, and surface transport errors deterministically.
5. Avoid duplicating agent logic—reuse current abstractions where possible.

## Candidate Designs
### 1. RemoteAgent Proxy
- Create `RemoteAgent` subclass sharing the Agent API but backed by a transport client that forwards prompts/history to a remote endpoint.
- Usage mirrors local agents, so existing pipe orchestrations work without code changes; remote responses stream back as `Message` objects.
- Pros: minimal orchestration changes, clear lifecycle; Cons: tighter coupling to OpenAI payload schema, multiple remote agents require multiple proxy instances.

### 2. Transport Adapter Layer
- Introduce `AgentTransport` protocol powering both local and remote messaging; e.g., `LocalLoopTransport`, `OpenAIChatTransport`.
- Agents and pipes depend on the protocol, so swapping transports (HTTP, websocket, a2a) is configuration-only.
- Pros: strong future-proofing, consistent observability; Cons: requires refactor of existing inter-agent plumbing.

### 3. Remote Agent Tool
- Package a remote conversation as an async tool (`remote_agent.invoke(...)`) that the LLM can call.
- Tool manages remote session state, parameter schemas, and returns structured responses; great for deterministic orchestration and telemetry.
- Pros: fits tool ecosystem, enforces typed contracts, easy to restrict capabilities; Cons: less seamless for streaming multi-turn dialogues, harder to compose with pipe operator.

### 4. Bridge Component Extension
- Build `RemoteBridge(AgentComponent)` that mirrors selected local messages to a remote agent session via hooks (before/after assistant messages) and injects remote replies into history.
- Allows different communication policies per mode/context without altering base agent.
- Pros: highly configurable, incremental adoption; Cons: component complexity, more implicit behavior.

### 5. Conversation Broker Resource
- Add a `ConversationBroker` resource managing long-lived remote sessions, capability discovery, retries, and multiplexing.
- Agents acquire broker handles and stream deltas (`async for chunk in broker.stream(...)`), enabling group chats and future transports.
- Pros: centralizes connection management, supports advanced topologies; Cons: new orchestration surface needs clear ergonomics.

## Evaluation Dimensions
- Developer ergonomics (API familiarity).
- Transport portability & extensibility.
- Streaming/multi-turn fidelity.
- Security/isolation concerns.
- Telemetry & auditability integration.

## Next Steps
1. Decide between Proxy vs Transport-layer refactor as the primary abstraction.
2. Prototype telemetry + error semantics for selected approach.
3. Plan complementary features (tool wrapper, broker) once base transport path is chosen.
4. Update DESIGN.md with chosen direction and TODOs before implementation.
