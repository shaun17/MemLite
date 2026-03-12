# memoLite OpenClaw Plugin

memoLite 的 OpenClaw 本地记忆插件。

## 功能

- `memory_search`
- `memolite_search`
- `memory_store`
- `memolite_store`
- `memory_forget`
- `memolite_forget`
- `memory_get`
- `memolite_get`
- `memory_list`
- `memolite_list`
- `autoCapture`
- `autoRecall`

`memory_*` 是通用入口，`memolite_*` 是显式绑定 MemoLite 的别名入口，便于上层代理在存在多个 memory provider 时直接点名调用。

## 本地安装

```bash
openclaw plugins install ./memoLite/integrations/openclaw
cd ./memoLite/integrations/openclaw
npm install
npm run build
```

## 配置

```json
{
  "openclaw-memolite": {
    "enabled": true,
    "config": {
      "baseUrl": "http://127.0.0.1:18731",
      "orgId": "openclaw",
      "projectId": "openclaw",
      "userId": "openclaw",
      "autoCapture": true,
      "autoRecall": true,
      "searchThreshold": 0.5,
      "topK": 5
    }
  }
}
```
