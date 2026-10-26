"""Remove native tools from reasoning turns and certify the local prompt surface."""
import json
from pathlib import Path

from council.diagnostics import DiagnosticRuntimeError


CONFIG = (
    'forced_login_method="chatgpt"', 'features.shell_tool=false',
    'features.multi_agent=false', 'agents.enabled=false',
    'features.multi_agent_v2={enabled=false,disable_native_tools=true}',
    'features.code_mode={enabled=false}', 'features.sleep_tool=false',
    'tools.experimental_request_user_input={enabled=false}',
    'features.view_image=false', 'features.image_generation=false',
    'features.apps=false', 'features.plugins=false', 'features.remote_plugin=false',
    'project_doc_max_bytes=0', 'web_search="disabled"', 'mcp_servers={}',
)
CAPABILITIES = dict(tool_mode=None, multi_agent_version=None,
    experimental_supported_tools=[], apply_patch_tool_type=None,
    node_repl_disabled=True, supports_search_tool=False)


def _json(data):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate field')
            value[key] = item
        return value

    def nonfinite(_):
        raise ValueError('Nonfinite value')

    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)


def prepare(executable, model, cwd, env, run):
    """Use bundled public metadata, never auth files or remote model discovery."""
    try:
        code, output, _ = run([executable, 'debug', 'models', '--bundled'],
            cwd=cwd, env=env, timeout=15)
        if code:
            raise ValueError('Catalog unavailable')
        catalog = _json(output)
        models = catalog['models']
        if type(models) is not list or any(type(item) is not dict for item in models):
            raise ValueError('Invalid catalog')
        selected = [item for item in models if item.get('slug') == model]
        if len(selected) != 1:
            raise ValueError('Exact model unavailable')
        # Preserve model identity, reasoning, context and every non-tool field.
        path = Path(cwd)/'reasoning-model.json'
        path.write_text(json.dumps({'models':[{**selected[0], **CAPABILITIES}]}), encoding='utf-8')
        config = [*CONFIG, 'model_catalog_json='+json.dumps(path.as_posix())]
        flags = [part for value in config for part in ('-c', value)]
        home = Path(cwd)/'inventory-home'
        home.mkdir()
        # debug has no --ignore-user-config. An empty diagnostic home gives it
        # equivalent local config isolation; no credentials are copied or used.
        code, output, _ = run([executable, '--no-daemon', *flags, '-c',
            'model='+json.dumps(model), 'debug', 'prompt-input', 'Tool isolation inventory.'],
            cwd=cwd, env={**env, 'CODEX_HOME':str(home)}, timeout=15)
        if code:
            raise ValueError('Inventory unavailable')
        items = _json(output)
        if type(items) is not list or not 1 <= len(items) <= 512:
            raise ValueError('Invalid inventory')
        for item in items:
            if type(item) is not dict or item.get('type') not in {'message', 'additional_tools'}:
                raise ValueError('Unknown inventory item')
            if item['type'] == 'additional_tools' and item.get('tools') != []:
                raise ValueError('Native tools exposed')
        return flags
    except PermissionError:
        raise
    except (ValueError, KeyError, TypeError, RecursionError):
        raise DiagnosticRuntimeError('CODEX_REVIEW_ISOLATION_FAILED') from None
