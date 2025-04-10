# Nutanix MCP Server  Key Name: MCP-demo-key
API Key: 

A Model Context Protocol (MCP) server for Nutanix Virtual Machine Management APIs.

## Features

- List images from Nutanix cluster
- Create new images in Nutanix cluster
- Secure credential management
- FastMCP integration

## Prerequisites

- Python 3.8 or higher
- Cursor IDE
- Nutanix Prism Central access
- Nutanix credentials

## Setup

1. Clone this repository:
```bash
git clone <repository-url>
cd nutanix-mcp
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your Nutanix credentials in `.env`

## Using with Cursor

1. Open the project in Cursor IDE
2. The MCP server will be automatically detected
3. Configure your environment variables in Cursor's settings
4. Use the MCP tools through Cursor's interface

## Available MCP Tools

### List Images
Lists all images available in the Nutanix cluster.

```python
list_images() -> List[Image]
```

### Create Image
Creates a new image in the Nutanix cluster.

```python
create_image(
    name: str,
    source_uri: str,
    description: Optional[str] = None,
    image_type: str = "DISK_IMAGE"
) -> Image
```

## Environment Variables

Required environment variables:
- `NUTANIX_USERNAME`: Your Nutanix username
- `NUTANIX_PASSWORD`: Your Nutanix password
- `NUTANIX_PRISM_CENTRAL_URL`: URL of your Prism Central instance

## Development

To run the MCP server locally:
```bash
mcp dev nutanix_mcp_server.py
```

## License

[Your License Here] 