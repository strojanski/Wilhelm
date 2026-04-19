#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="my_secret_key_123"
MODEL="google/gemma-4-e4b-it"

echo "==============================="
echo " Gemma API Deployment Check"
echo "==============================="

# 1. Health check
echo ""
echo "[ 1 ] Health check"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL/health)
if [ "$HEALTH" = "200" ]; then
  echo "✅ Server is healthy"
else
  echo "❌ Health check failed (HTTP $HEALTH) — is the container running?"
  echo "   Run: docker compose logs -f inference"
  exit 1
fi

# 2. Auth check
echo ""
echo "[ 2 ] API key auth"
AUTH=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL/v1/models)
AUTHOK=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $API_KEY" $BASE_URL/v1/models)
if [ "$AUTH" = "401" ] && [ "$AUTHOK" = "200" ]; then
  echo "✅ Auth working correctly (rejects without key, accepts with key)"
elif [ "$AUTHOK" = "200" ]; then
  echo "✅ API key accepted"
else
  echo "❌ Auth issue (HTTP $AUTHOK)"
fi

# 3. Model loaded
echo ""
echo "[ 3 ] Model loaded"
MODELS=$(curl -s -H "Authorization: Bearer $API_KEY" $BASE_URL/v1/models)
if echo "$MODELS" | grep -q "$MODEL"; then
  echo "✅ Model $MODEL is loaded"
else
  echo "❌ Model not found in response:"
  echo "$MODELS"
fi

# 4. Text completion
echo ""
echo "[ 4 ] Text completion"
RESPONSE=$(curl -s -X POST $BASE_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Reply with one word: hello\"}],
    \"max_tokens\": 10
  }")
if echo "$RESPONSE" | grep -q "content"; then
  REPLY=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])")
  echo "✅ Got response: $REPLY"
else
  echo "❌ No valid response:"
  echo "$RESPONSE"
fi

# 5. Image input
echo ""
echo "[ 5 ] Image processing"
IMGRESPONSE=$(curl -s -X POST $BASE_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"image_url\", \"image_url\": {\"url\": \"https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png\"}},
        {\"type\": \"text\", \"text\": \"What is in this image? Reply in one sentence.\"}
      ]
    }],
    \"max_tokens\": 50
  }")
if echo "$IMGRESPONSE" | grep -q "content"; then
  IMGREPLY=$(echo "$IMGRESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])")
  echo "✅ Image response: $IMGREPLY"
else
  echo "❌ Image processing failed:"
  echo "$IMGRESPONSE"
fi

# 6. GPU usage
echo ""
echo "[ 6 ] GPU utilization"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader

echo ""
echo "==============================="
echo " Done"
echo "==============================="