"""
antigravity_telemetry.parser: Zero-dependency wire-format Google Protocol Buffers decoder.

Decodes Antigravity runtime telemetry payloads from SQLite `steps.metadata`,
`steps.step_payload`, and `steps.error_details` blobs.
"""

from typing import Any, Dict, List, Optional, Tuple
import datetime
import json
import re


def parse_wire_fields(b: bytes) -> List[Tuple[int, str, Any]]:
    """
    Parse a raw protobuf byte stream into field tuples:
    (field_number, wire_type_name, value).
    """
    i = 0
    fields = []
    length = len(b)

    while i < length:
        # Read varint key
        key = 0
        shift = 0
        while True:
            if i >= length:
                return fields
            byte = b[i]
            i += 1
            key |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break

        field_num = key >> 3
        wire_type = key & 0x7

        if wire_type == 0:  # Varint
            val = 0
            shift = 0
            while True:
                if i >= length:
                    return fields
                byte = b[i]
                i += 1
                val |= (byte & 0x7F) << shift
                shift += 7
                if not (byte & 0x80):
                    break
            fields.append((field_num, "varint", val))

        elif wire_type == 1:  # 64-bit
            val = b[i : i + 8]
            i += 8
            fields.append((field_num, "fixed64", val))

        elif wire_type == 2:  # Length-delimited (bytes, string, embedded message)
            str_len = 0
            shift = 0
            while True:
                if i >= length:
                    return fields
                byte = b[i]
                i += 1
                str_len |= (byte & 0x7F) << shift
                shift += 7
                if not (byte & 0x80):
                    break
            val = b[i : i + str_len]
            i += str_len
            fields.append((field_num, "bytes", val))

        elif wire_type == 5:  # 32-bit
            val = b[i : i + 4]
            i += 4
            fields.append((field_num, "fixed32", val))

        else:
            # Unknown wire type, abort further parsing
            break

    return fields


# Public alias for pure-Python wire protobuf decoding
decode_wire_protobuf = parse_wire_fields


def extract_step_telemetry(metadata_bytes: Optional[bytes]) -> Optional[Dict[str, Any]]:
    """
    Extract usage metadata from `steps.metadata` blob.

    Returns structured dictionary with:
    - timestamp: ISO 8601 string
    - model_id: int or str
    - prompt_tokens_uncached: int
    - cached_tokens: int
    - total_input_tokens: int
    - output_tokens_total: int
    - thinking_tokens: int
    - answer_tokens: int
    - cache_hit_ratio_pct: float
    - response_id: str
    - agent_id: str
    - session_id: str
    """
    if not metadata_bytes or len(metadata_bytes) == 0:
        return None

    top_fields = parse_wire_fields(metadata_bytes)

    # 1. Extract Timestamp from Field 1
    timestamp_iso: Optional[str] = None
    for fnum, ftype, val in top_fields:
        if fnum == 1 and ftype == "bytes":
            sub = parse_wire_fields(val)
            seconds = 0
            nanos = 0
            for sfnum, sftype, sval in sub:
                if sfnum == 1 and sftype == "varint":
                    seconds = sval
                elif sfnum == 2 and sftype == "varint":
                    nanos = sval
            if seconds > 0:
                dt = datetime.datetime.fromtimestamp(seconds + (nanos / 1e9), tz=datetime.timezone.utc)
                timestamp_iso = dt.isoformat()
            break

    # 2. Extract Usage Metadata from Field 9
    usage_fields = None
    for fnum, ftype, val in top_fields:
        if fnum == 9 and ftype == "bytes":
            usage_fields = parse_wire_fields(val)
            break

    if not usage_fields:
        return None

    model_id = None
    uncached_prompt = 0
    total_output = 0
    cached_prompt = 0
    thinking_tokens = 0
    answer_tokens = 0
    agent_id = ""
    session_id = ""
    response_id = ""

    for sfnum, sftype, sval in usage_fields:
        if sfnum == 1 and sftype == "varint":
            model_id = sval
        elif sfnum == 2 and sftype == "varint":
            uncached_prompt = sval
        elif sfnum == 3 and sftype == "varint":
            total_output = sval
        elif sfnum == 5 and sftype == "varint":
            cached_prompt = sval
        elif sfnum == 7 and sftype == "bytes":
            try:
                agent_id = sval.decode("utf-8", errors="replace")
            except (UnicodeDecodeError, AttributeError):
                agent_id = ""
        elif sfnum == 8 and sftype == "bytes":
            try:
                sub_8 = {s8_fn: s8_val for s8_fn, s8_wt, s8_val in parse_wire_fields(sval)}
                if 2 in sub_8 and isinstance(sub_8[2], bytes):
                    session_id = sub_8[2].decode("utf-8", errors="replace")
                elif 1 in sub_8 and isinstance(sub_8[1], bytes) and sub_8[1] != b"sessionID":
                    session_id = sub_8[1].decode("utf-8", errors="replace")
                else:
                    decoded = sval.decode("utf-8", errors="replace")
                    session_id = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", decoded).replace("sessionID", "").strip()
            except (ValueError, KeyError, UnicodeDecodeError, AttributeError):
                session_id = ""
        elif sfnum == 9 and sftype == "varint":
            thinking_tokens = sval
        elif sfnum == 10 and sftype == "varint":
            answer_tokens = sval
        elif sfnum == 11 and sftype == "bytes":
            try:
                response_id = sval.decode("utf-8", errors="replace")
            except (UnicodeDecodeError, AttributeError):
                response_id = ""

    total_input = uncached_prompt + cached_prompt
    cache_hit_ratio_pct = (cached_prompt / total_input * 100.0) if total_input > 0 else 0.0

    # Sanity reconcile for answer tokens if missing
    if answer_tokens == 0 and total_output >= thinking_tokens:
        answer_tokens = total_output - thinking_tokens

    return {
        "timestamp": timestamp_iso,
        "model_id": str(model_id) if model_id is not None else "unknown",
        "prompt_tokens_uncached": uncached_prompt,
        "cached_tokens": cached_prompt,
        "total_input_tokens": total_input,
        "output_tokens_total": total_output,
        "thinking_tokens": thinking_tokens,
        "answer_tokens": answer_tokens,
        "cache_hit_ratio_pct": round(cache_hit_ratio_pct, 2),
        "response_id": response_id,
        "agent_id": agent_id,
        "session_id": session_id,
    }


def extract_step_payload_details(
    step_payload_bytes: Optional[bytes],
    step_type: int = 0,
) -> Dict[str, Any]:
    """
    Extract decoded text, model thinking, tool calls, and subagent references
    from raw `steps.step_payload` blob without external protobuf dependencies.
    """
    if not step_payload_bytes:
        return {
            "payload_text": "",
            "user_text": "",
            "answer_text": "",
            "thinking_text": "",
            "system_text": "",
            "tool_calls": [],
            "tool_calls_json": "[]",
            "subagents_spawned": [],
            "subagent_recipients": [],
            "swarm_actions": [],
            "swarm_mentions": [],
            "skills_referenced": [],
        }

    top_fields = parse_wire_fields(step_payload_bytes)
    top_dict: Dict[int, List[Tuple[str, Any]]] = {}
    for fnum, ftype, val in top_fields:
        if fnum not in top_dict:
            top_dict[fnum] = []
        top_dict[fnum].append((ftype, val))

    user_text = ""
    answer_text = ""
    thinking_text = ""
    system_text = ""
    tool_calls = []
    subagents_spawned = []
    subagent_recipients = []
    swarm_actions = []
    swarm_mentions = []
    skills_referenced = set()

    # 1. User prompt text from field 19
    if 19 in top_dict:
        for ftype, val in top_dict[19]:
            if ftype == "bytes":
                for sf, st, sv in parse_wire_fields(val):
                    if sf == 2 and isinstance(sv, bytes):
                        user_text = sv.decode("utf-8", errors="replace")

    # 2. Assistant response and thinking traces from field 20
    if 20 in top_dict:
        for ftype, val in top_dict[20]:
            if ftype == "bytes":
                for sf, st, sv in parse_wire_fields(val):
                    if sf in (1, 8) and isinstance(sv, bytes):
                        answer_text = sv.decode("utf-8", errors="replace")
                    elif sf == 3 and isinstance(sv, bytes):
                        thinking_text = sv.decode("utf-8", errors="replace")

    # 3. System / Subagent message from field 114
    sender_id = ""
    if 114 in top_dict:
        for ftype, val in top_dict[114]:
            if ftype == "bytes":
                for sf, st, sv in parse_wire_fields(val):
                    if sf == 1 and isinstance(sv, bytes):
                        system_text = sv.decode("utf-8", errors="replace")
                        sm = re.search(r"sender=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", system_text)
                        if sm:
                            sender_id = sm.group(1)

    # 4. Tool calls and execution metadata from field 5 and field 140
    tool_meta_map: Dict[str, str] = {}
    result_preview = ""
    if 140 in top_dict:
        for ftype, val in top_dict[140]:
            if ftype == "bytes":
                for sf, st, sv in parse_wire_fields(val):
                    if sf == 1 and isinstance(sv, bytes):
                        kvs = parse_wire_fields(sv)
                        kv_strs = [kv.decode("utf-8", errors="replace") for kf, kt, kv in kvs if kt == "bytes"]
                        if len(kv_strs) >= 2:
                            tool_meta_map[kv_strs[0]] = kv_strs[1]
                    elif sf == 2 and isinstance(sv, bytes):
                        result_preview = sv.decode("utf-8", errors="replace")

    if 5 in top_dict:
        for ftype, val in top_dict[5]:
            if ftype == "bytes":
                for sf, st, sv in parse_wire_fields(val):
                    if sf == 4 and isinstance(sv, bytes):
                        call_fields = parse_wire_fields(sv)
                        cid = ""
                        name = ""
                        args = ""
                        for cf, ct, cv in call_fields:
                            if cf == 1 and isinstance(cv, bytes):
                                cid = cv.decode("utf-8", errors="replace")
                            elif cf == 2 and isinstance(cv, bytes):
                                name = cv.decode("utf-8", errors="replace")
                            elif cf == 3 and isinstance(cv, bytes):
                                args = cv.decode("utf-8", errors="replace")
                        if cid or name:
                            tool_calls.append({
                                "call_id": cid,
                                "tool_name": name,
                                "arguments_json": args,
                                "tool_action": tool_meta_map.get("toolAction", ""),
                                "tool_summary": tool_meta_map.get("toolSummary", ""),
                                "result_summary": result_preview[:500] if result_preview else "",
                            })

    # Subagent & native swarm discovery from invoke_subagent, send_message, swarm, or post_message
    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
    convo_id_pattern = re.compile(r'"conversationId":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', re.IGNORECASE)
    recipient_pattern = re.compile(r'"Recipient":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', re.IGNORECASE)
    mention_pattern = re.compile(r"(?<![a-zA-Z0-9._+-])@([a-zA-Z0-9][a-zA-Z0-9_-]*)")

    for tc in tool_calls:
        name = tc["tool_name"]
        args = tc.get("arguments_json", "")
        res = tc.get("result_summary", "")
        if "invoke_subagent" in name:
            found = convo_id_pattern.findall(res)
            if not found:
                found = uuid_pattern.findall(res)
            subagents_spawned.extend(found)
        elif "send_message" in name:
            found = recipient_pattern.findall(args)
            if not found and "Recipient" in tool_meta_map:
                found = [tool_meta_map["Recipient"]]
            subagent_recipients.extend(found)
        elif name == "swarm" or name.endswith(":swarm"):
            try:
                parsed_args = json.loads(args) if args else {}
            except (json.JSONDecodeError, TypeError):
                parsed_args = {}
            if isinstance(parsed_args, dict):
                swarm_actions.append({
                    "action": str(parsed_args.get("action", "")),
                    "name": str(parsed_args.get("name", "")),
                    "model": str(parsed_args.get("model", "")),
                    "fork": str(parsed_args.get("fork", "")),
                    "workspace": str(parsed_args.get("workspace", "")),
                    "n": parsed_args.get("n"),
                    "tasks": parsed_args.get("tasks") if isinstance(parsed_args.get("tasks"), list) else [],
                })
        elif name == "post_message" or name.endswith(":post_message"):
            try:
                parsed_args = json.loads(args) if args else {}
            except (json.JSONDecodeError, TypeError):
                parsed_args = {}
            if isinstance(parsed_args, dict):
                msg_text = str(parsed_args.get("text", ""))
                if msg_text:
                    swarm_mentions.extend(mention_pattern.findall(msg_text))

    # Check for skill references
    skill_pattern = re.compile(r"skills/([a-zA-Z0-9][a-zA-Z0-9_-]{1,63})/SKILL\.md")
    for text_blob in (user_text, answer_text, system_text, result_preview):
        for sk in skill_pattern.findall(text_blob):
            skills_referenced.add(sk)
    for tc in tool_calls:
        for sk in skill_pattern.findall(tc.get("arguments_json", "")):
            skills_referenced.add(sk)

    # Compile unified payload_text for full-text search
    if answer_text and thinking_text:
        payload_text = f"{thinking_text}\n\n{answer_text}".strip()
    elif answer_text:
        payload_text = answer_text
    elif thinking_text:
        payload_text = thinking_text
    elif user_text:
        payload_text = user_text
    elif system_text:
        payload_text = system_text
    elif tool_calls:
        payload_text = "\n".join(
            f"[{tc['tool_name']}] {tc.get('tool_action') or tc.get('tool_summary') or tc.get('arguments_json')}"
            for tc in tool_calls
        )
    else:
        payload_text = ""

    return {
        "payload_text": payload_text,
        "user_text": user_text,
        "answer_text": answer_text,
        "thinking_text": thinking_text,
        "system_text": system_text,
        "tool_calls": tool_calls,
        "tool_calls_json": json.dumps(tool_calls),
        "sender_id": sender_id,
        "subagents_spawned": list(dict.fromkeys(subagents_spawned)),
        "subagent_recipients": list(dict.fromkeys(subagent_recipients)),
        "swarm_actions": swarm_actions,
        "swarm_mentions": list(dict.fromkeys(swarm_mentions)),
        "skills_referenced": sorted(skills_referenced),
    }


def extract_error_details(error_bytes: Optional[bytes]) -> str:
    """Extract human-readable error text from steps.error_details blob."""
    if not error_bytes:
        return ""
    try:
        fields = parse_wire_fields(error_bytes)
        for fnum, ftype, val in fields:
            if ftype == "bytes":
                try:
                    s = val.decode("utf-8", errors="replace")
                    if len(s) > 0 and any(c.isalpha() for c in s):
                        return s
                except (UnicodeDecodeError, AttributeError):
                    pass
        return error_bytes.decode("utf-8", errors="replace")
    except (ValueError, IndexError, UnicodeDecodeError, AttributeError):
        return ""


def extract_trajectory_metadata(metadata_bytes: Optional[bytes]) -> Dict[str, Any]:
    """
    Extract conversation trajectory metadata from raw `trajectory_metadata_blob` wire bytes.

    Extracts:
    - raw_workspace_uri: str
    - git_branch: str
    - convo_id: str
    - agent_name: str ("auditor", "implementer", "default", etc.)
    - agent_description: str
    - agent_config_uri: str
    - is_subagent: bool
    - parent_convo_id: str
    - subagent_type: str
    - subagent_role: str
    """
    if not metadata_bytes or len(metadata_bytes) == 0:
        return {
            "raw_workspace_uri": "",
            "git_branch": "main",
            "convo_id": "",
            "agent_name": "default",
            "agent_description": "",
            "agent_config_uri": "",
            "is_subagent": False,
            "parent_convo_id": "",
            "subagent_type": "",
            "subagent_role": "",
        }

    fields = parse_wire_fields(metadata_bytes)
    f_map = {fn: val for fn, wt, val in fields}

    raw_ws = ""
    git_branch = "main"
    convo_id = ""
    agent_name = "default"
    agent_description = ""
    agent_config_uri = ""
    is_subagent = False
    parent_convo_id = ""
    subagent_type = ""
    subagent_role = ""

    # Field 1: workspace and branch
    if 1 in f_map and isinstance(f_map[1], bytes):
        for sfn, swt, sval in parse_wire_fields(f_map[1]):
            if sfn == 1 and isinstance(sval, bytes):
                raw_ws = sval.decode("utf-8", errors="replace").strip()
            elif sfn == 4 and isinstance(sval, bytes):
                git_branch = sval.decode("utf-8", errors="replace").strip()

    # Field 7: fallback workspace URI
    if not raw_ws and 7 in f_map and isinstance(f_map[7], bytes):
        raw_ws = f_map[7].decode("utf-8", errors="replace").strip()

    # Field 6: convo_id
    if 6 in f_map and isinstance(f_map[6], bytes):
        convo_id = f_map[6].decode("utf-8", errors="replace").strip()

    # Field 17: subagent flag
    if 17 in f_map and f_map[17] == 1:
        is_subagent = True

    # Field 5: parent convo ID
    if 5 in f_map and isinstance(f_map[5], bytes):
        parent_convo_id = f_map[5].decode("utf-8", errors="replace").strip()

    # Field 8: subagent invocation spec (type, role, prompt)
    if 8 in f_map and isinstance(f_map[8], bytes):
        for sfn, swt, sval in parse_wire_fields(f_map[8]):
            if sfn == 1 and isinstance(sval, bytes):
                subagent_type = sval.decode("utf-8", errors="replace").strip()
            elif sfn == 2 and isinstance(sval, bytes):
                subagent_role = sval.decode("utf-8", errors="replace").strip()

    # Field 4: agent persona definition (custom main agent)
    if 4 in f_map and isinstance(f_map[4], bytes):
        for sfn, swt, sval in parse_wire_fields(f_map[4]):
            if sfn == 1 and isinstance(sval, bytes):
                agent_name = sval.decode("utf-8", errors="replace").strip()
            elif sfn == 8 and isinstance(sval, bytes):
                agent_description = sval.decode("utf-8", errors="replace").strip()

    # Field 10: agent config URI and system prompt
    if 10 in f_map and isinstance(f_map[10], bytes):
        for sfn, swt, sval in parse_wire_fields(f_map[10]):
            if isinstance(sval, bytes):
                for ssfn, sswt, ssval in parse_wire_fields(sval):
                    if isinstance(ssval, bytes) and (ssval.startswith(b"file://") or ssval.endswith(b".md") or ssval.endswith(b".json")):
                        agent_config_uri = ssval.decode("utf-8", errors="replace").strip()
                        break
            if agent_config_uri:
                break

    return {
        "raw_workspace_uri": raw_ws,
        "git_branch": git_branch or "main",
        "convo_id": convo_id,
        "agent_name": agent_name or "default",
        "agent_description": agent_description,
        "agent_config_uri": agent_config_uri,
        "is_subagent": is_subagent,
        "parent_convo_id": parent_convo_id,
        "subagent_type": subagent_type,
        "subagent_role": subagent_role,
    }

