# memoLite OpenClaw Plugin

memoLite 的 OpenClaw 本地记忆插件。

## 功能

- `memory_search`
- `memory_store`
- `memory_forget`
- `memory_get`
- `memory_list`
- `autoCapture`
- `autoRecall`

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
      "baseUrl": "http://127.0.0.1:8080",
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
