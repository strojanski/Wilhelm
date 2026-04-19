import argparse
from openai import OpenAI


def create_client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def chat(
    client: OpenAI,
    model: str,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Call a remote OpenAI-compatible server.")
    parser.add_argument("--base-url", default="http://localhost:8000/v1", help="Base URL of the remote server")
    parser.add_argument("--api-key", default="EMPTY", help="API key for the server")
    parser.add_argument("--model", default="google/gemma-4-E4B-it", help="Model name to use")
    parser.add_argument("--prompt", default="Write me a pdf with medical report of a hand fracture.", help="Prompt to send to the model")
    parser.add_argument("--max-tokens", type=int, default=512, help="Maximum number of tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    args = parser.parse_args()



    client = create_client(base_url=args.base_url, api_key=args.api_key)

    print(f"Connecting to: {args.base_url}")
    print(f"Model:         {args.model}")
    print(f"Prompt:        {args.prompt}")
    print("-" * 50)

    reply = chat(
        client=client,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )

    print(reply)


if __name__ == "__main__":
    main()