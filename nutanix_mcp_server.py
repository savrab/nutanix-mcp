import os
from typing import List, Optional
from fastmcp import FastMCP
from dotenv import load_dotenv
import ntnx_vmm_py_client
from ntnx_vmm_py_client import (
    Configuration, ApiClient, ImagesApi, Image, ImageType, UrlSource, VmApi, rest,
    CreateVmApiResponse
)
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.Vm import Vm
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.CdRom import CdRom
# from ntnx_vmm_py_client.models.vmm.v4.ahv.config.Disk import Disk
# from ntnx_vmm_py_client.models.vmm.v4.ahv.config.DiskAddress import DiskAddress
# from ntnx_vmm_py_client.models.vmm.v4.ahv.config.VmDisk import VmDisk
# from ntnx_vmm_py_client.models.vmm.v4.ahv.config.DiskBusType import DiskBusType
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.CdRomAddress import CdRomAddress
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.CdRomBusType import CdRomBusType
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.VmSourceReference import VmSourceReference
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.VmSourceReferenceEntityType import VmSourceReferenceEntityType
from ntnx_vmm_py_client.models.vmm.v4.ahv.config.ClusterReference import ClusterReference
import ntnx_monitoring_py_client
from ntnx_monitoring_py_client import (ClusterLogsApi, ApiClient, api_response, Configuration, rest)
from ntnx_monitoring_py_client.models.monitoring.v4.serviceability.LogCollectionSpec import LogCollectionSpec
from ntnx_monitoring_py_client.models.monitoring.v4.serviceability.NtnxServerUploadParams import NtnxServerUploadParams
from ntnx_monitoring_py_client.models.monitoring.v4.serviceability.ServerUploadProtocol import ServerUploadProtocol
from ntnx_monitoring_py_client.models.monitoring.v4.serviceability.Alert import Alert
import logging
import httpx
import base64
import uuid
from datetime import datetime
import re


# Load environment variables
load_dotenv()

# Configure logging
# log_filename = f"nutanix_mcp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler(log_filename),
#         logging.StreamHandler()  # This will keep console output
#     ]
# )

# logger = logging.getLogger(__name__)
# logger.info(f"Logging initialized. Log file: {log_filename}")

class NutanixConfig:
    def __init__(self):
        self.username = os.getenv("NUTANIX_USERNAME")
        self.password = os.getenv("NUTANIX_PASSWORD")
        self.prism_central_url = os.getenv("NUTANIX_PRISM_CENTRAL_URL")
        self.cluster_uuid = os.getenv("CLUSTER_UUID")

    def get_client_config(self, client_module_name: str):
        """Get configured API client for any Nutanix module
        
        Args:
            client_module_name: Name of the Nutanix client module (e.g., "vmm", "monitoring")
            
        Returns:
            Tuple of (ApiClient, Configuration)
            
        Raises:
            ValueError: If the client module is not found or invalid
        """
        try:
            # Dynamically import the client module
            module_name = f"ntnx_{client_module_name}_py_client"
            client_module = __import__(module_name)
            
            # Get the Configuration and ApiClient classes
            ConfigClass = getattr(client_module, "Configuration")
            ApiClientClass = getattr(client_module, "ApiClient")
            
            # Create and configure the client
            config = ConfigClass()
            config.host = self.prism_central_url.replace("https://", "").split(":")[0]
            config.port = int(self.prism_central_url.split(":")[-1])
            config.username = self.username
            config.password = self.password
            config.max_retry_attempts = 3
            config.backoff_factor = 3
            config.verify_ssl = False
            
            # Create the client
            client = ApiClientClass(configuration=config)
            
            return client, config
            
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Invalid client module '{client_module_name}': {str(e)}")

config = NutanixConfig()
http_client = httpx.AsyncClient(verify=False)  # Disable SSL verification for self-signed certificates

mcp = FastMCP(title="Nutanix MCP Server")

@mcp.tool()
async def list_images():
    """List all images available in the Nutanix cluster."""
    # Check required environment variables
    if not all([config.username, config.password, config.prism_central_url]):
        raise ValueError("Missing required environment variables: NUTANIX_USERNAME, NUTANIX_PRISM_CENTRAL_URL, NUTANIX_PASSWORD, or NUTANIX_PRIVATE_KEY_PATH")
    
    # Get configured client
    client, _ = config.get_client_config("vmm")
    images_api = ntnx_vmm_py_client.ImagesApi(api_client=client)
    
    try:
        # List images with pagination
        api_response = images_api.list_images(_page=0, _limit=50)
        # logger.info(f"API Response Type: {type(api_response)}")
        
        if not api_response:
            # logger.error("No response from API")
            return {"error": "No response from API"}
            
        if not hasattr(api_response, 'data') or not api_response.data:
            # logger.error("No data in response")
            return {"error": "No images found in response"}
            
        images = []
        for img in api_response.data:
            try:
                image_data = {
                    "name": img.name,
                    "size_bytes": img.size_bytes,
                    "type": img.type
                }
                # logger.info(f"Processed image data: {image_data}")
                images.append(image_data)
            except Exception as e:
                # logger.error(f"Error processing image: {str(e)}")
                continue
                
        if not images:
            # logger.warning("No valid images found in the response")
            return {"error": "No valid images found"}
            
        return images
        
    except rest.ApiException as e:
        # logger.error(f"API Exception: {str(e)}")
        return {"error": f"Failed to list images: {str(e)}"}
    except Exception as e:
        # logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@mcp.tool()
async def create_image(name: str, source_uri: str, description: Optional[str] = None, image_type: str = "ISO_IMAGE"):
    """Create a new image in the Nutanix cluster
    
    Args:
        name: Name of the new image
        source_uri: URI of the image source (e.g., http://path/to/iso)
        description: Optional description of the image
        image_type: Type of image (DISK_IMAGE, ISO_IMAGE, etc.)
        
    Returns:
        Dict containing the created image details and task reference
    """
    # Check required environment variables
    if not all([config.username, config.password, config.prism_central_url]):
        raise ValueError("Missing required environment variables")
    
    # Get configured client
    client, _ = config.get_client_config("vmm")
    images_api = ntnx_vmm_py_client.ImagesApi(api_client=client)
    image = ntnx_vmm_py_client.Image()
    source_uri = ntnx_vmm_py_client.UrlSource(url=source_uri, allow_insecure=True)
    
    try:
        # Initialize image object
        image.name = name  # required field
        image.type = ntnx_vmm_py_client.ImageType.ISO_IMAGE # required field
        if description:
            image.description = description
        image.source = source_uri
        
        # Create image using SDK
        api_response = images_api.create_image(body=image)
        if not api_response:
            return {"error": "Failed to create image: Invalid response"}
            
        # Extract task reference details
        task_ref = api_response.metadata
        return {
            "status": "Image creation initiated",
        }
        
    except rest.ApiException as e:
        return {"error": f"Failed to create image: {str(e)}"}

@mcp.tool()
async def create_vm(
    name: str,
    description: str,
    num_sockets: int,
    num_cores_per_socket: int,
    memory_size_gb: float
):
    """Create a new VM in the Nutanix cluster
    
    Args:
        name: Name of the VM
        description: Description of the VM
        num_sockets: Number of CPU sockets
        num_cores_per_socket: Number of cores per socket
        memory_size_gb: Memory size in gigabytes (minimum 0.064 GB = 64MB)
    Returns:
        VM creation initiated
    """
    # Check required environment variables
    if not all([config.username, config.password, config.prism_central_url]):
        raise ValueError("Missing required environment variables")
    
    # Convert GB to bytes and validate memory size (minimum 64MB = 0.064 GB)
    MIN_MEMORY_GB = 0.064  # 64MB in GB
    if memory_size_gb < MIN_MEMORY_GB:
        return {"error": f"Memory size must be at least 0.064 GB (64MB). Provided: {memory_size_gb} GB"}
    
    memory_size_bytes = int(memory_size_gb * 1024 * 1024 * 1024)  # Convert GB to bytes
    
    # Get configured client
    client, _ = config.get_client_config("vmm")
    vm_api = ntnx_vmm_py_client.VmApi(api_client=client)
    
    try:
        # Generate a UUID for the VM first
        vm_uuid = str(uuid.uuid4())
        
        # Create VM spec
        vm_spec = Vm()
        vm_spec.name = name
        vm_spec.description = description
        
        # Set cluster reference with validated UUID
        vm_spec.cluster = ClusterReference(ext_id=config.cluster_uuid)
        
        # Configure CPU and memory
        vm_spec.num_sockets = num_sockets
        vm_spec.num_cores_per_socket = num_cores_per_socket
        vm_spec.memory_size_bytes = memory_size_bytes
        
        # Set source reference
        vm_spec.source = VmSourceReference(
            entity_type=VmSourceReferenceEntityType.VM,
            ext_id=vm_uuid
        )
        
        # Configure CD-ROM
        vm_spec.cdrom = CdRom(cdrom_address=CdRomAddress(bus_type=CdRomBusType.IDE, index=None))
        
        # Create VM using SDK
        api_response = vm_api.create_vm(body=vm_spec)
        if not api_response:
            return {"error": "Failed to create VM: Invalid response"}
            
        # Extract task reference details
        return {"status": "VM creation initiated"}
        
    except rest.ApiException as e:
        return {"error": f"Failed to create VM: {str(e)}"}
  
    

@mcp.tool()
async def get_logs(start_time: str, end_time: str, case_number: int):
    """Get the logs from the Nutanix cluster
    
    Args:
        start_time: Start time in format like '31 march 12 AM' or '31 march 2025 12:00 AM'
        end_time: End time in format like '31 march 1 AM' or '31 march 2025 1:00 AM'
    """
    # Check required environment variables
    if not all([config.username, config.password, config.prism_central_url]):
        raise ValueError("Missing required environment variables")
    
    def convert_to_iso_format(time_str: str) -> str:
        """Convert user-friendly time format to ISO format"""
        from datetime import datetime
        import re
        
        # Try different date formats
        formats = [
            '%d %B %Y %I %p',          # 31 march 2025 12 AM
            '%d %B %Y %I:%M %p',       # 31 march 2025 12:00 AM
            '%d %B %I %p',             # 31 march 12 AM
            '%d %B %I:%M %p',          # 31 march 12:00 AM
        ]
        
        # If year is not specified, use current year
        if not re.search(r'\d{4}', time_str):
            current_year = datetime.now().year
            time_str = f"{time_str} {current_year}"
        
        # Try parsing with each format
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                continue
        
        raise ValueError(f"Invalid time format: {time_str}. Use formats like '31 march 12 AM' or '31 march 2025 12:00 AM'")
    
    try:
        # Convert user-friendly formats to ISO format
        iso_start_time = convert_to_iso_format(start_time)
        iso_end_time = convert_to_iso_format(end_time)
        
        # Validate time range
        start = datetime.strptime(iso_start_time, '%Y-%m-%dT%H:%M:%SZ')
        end = datetime.strptime(iso_end_time, '%Y-%m-%dT%H:%M:%SZ')
        if end <= start:
            return {"error": "End time must be after start time"}
            
    except ValueError as e:
        return {"error": str(e)}
    
    # Get configured client
    client, _ = config.get_client_config("monitoring")
    cluster_logs_api = ntnx_monitoring_py_client.ClusterLogsApi(api_client=client)
    log_collection_spec = ntnx_monitoring_py_client.LogCollectionSpec()
    
   
    log_collection_spec.archive_opts = ntnx_monitoring_py_client.ArchiveOpts(
        archive_name='NTNX-Log',
        upload_params=NtnxServerUploadParams(case_number=case_number, protocol=ServerUploadProtocol.FTP)
    )
    log_collection_spec.start_time = iso_start_time
    log_collection_spec.end_time = iso_end_time
    
    try:
        api_response = cluster_logs_api.collect_logs(extId=config.cluster_uuid, body=log_collection_spec)
        return {"status": "Logs collection initiated"}
    except rest.ApiException as e:
        return {"error": f"Failed to collect logs: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
    
@mcp.tool()
async def get_alerts():
    """Get the alerts from the Nutanix cluster."""
    
    
    # Check required environment variables
    if not all([config.username, config.password, config.prism_central_url]):
        raise ValueError("Missing required environment variables")
    
    # Get configured client
    client, _ = config.get_client_config("monitoring")
    alerts_api = ntnx_monitoring_py_client.AlertsApi(api_client=client)
    
    try:
       
        api_response = alerts_api.list_alerts(_page=0, _limit=10)
               
        if not api_response or not hasattr(api_response, 'data'):
            error_msg = "Invalid response from alerts API"
            return {"error": error_msg}
                    
        return {"status": "Alerts retrieved",
                "alerts": api_response.data}
    except rest.ApiException as e:
        error_msg = f"Failed to retrieve alerts: {str(e)}"
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        return {"error": error_msg}
    

if __name__ == "__main__":
    import uvicorn
    import sys
    print(f"Python path: {sys.executable}")
    print(f"Python version: {sys.version}")
    print("Starting MCP server...")
    mcp.run(transport="stdio")
