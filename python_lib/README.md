# Stoilo

Python client for the Stoilo service.

## Installation

```bash
pip install -e .[dev]  # Install in development mode with dev dependencies
```

## Usage

Basic usage example:

```python
import asyncio
import stoilo


async def main():
    conn = await stoilo.connect('localhost:57010')
    
    task = conn.create_task(
        kwargs={"a": 2, "b": 3},
        func=lambda kwargs: kwargs["a"] + kwargs["b"]
    )
    
    result = await task.submit()
    print(f"Task result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

See the examples directory for more usage examples.
