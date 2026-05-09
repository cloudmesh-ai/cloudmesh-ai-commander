# Cloudmesh AI Commander

The `cloudmesh-ai-commander` extension provides a set of automation tools to orchestrate the deployment, management, and access of AI model servers on the UVA GPU cluster.

It simplifies the complex process of requesting compute resources via iJob, deploying server software (either mock or real), and establishing secure SSH tunnels for local access.

## Documentation Guides

Depending on your needs, please refer to the appropriate guide:

### 1. [Mock Server Guide](README-mock.md)
**Purpose**: Rapid development and testing.
- **What it does**: Deploys a lightweight FastAPI mock server that simulates the vLLM API.
- **When to use**: When you need to test your application's integration with an AI API without consuming expensive GPU resources or waiting for large model weights to load.
- **Key Command**: `cmc commander run mock`

### 2. [Real Gemma Service Guide](README-gemma.md)
**Purpose**: Production-grade model serving.
- **What it does**: Deploys the actual **Gemma 4** model using the **vLLM** engine via Apptainer containers on UVA GPU nodes.
- **When to use**: When you need actual model inferences, high-throughput serving, and real GPU performance.
- **Key Command**: `cmc commander run vllm`

---

## Comparison at a Glance

| Feature | Mock Workflow | Real Gemma Workflow |
| :--- | :--- | :--- |
| **Resource Usage** | Minimal (CPU/Small RAM) | High (Multiple A100 GPUs) |
| **Startup Time** | Seconds | Minutes (Model Loading) |
| **Accuracy** | Simulated Responses | Actual LLM Inferences |
| **Deployment** | Python Script | Apptainer Container |
| **Primary Goal** | API Integration Testing | Model Evaluation & Usage |

## Quick Installation

To get started with the commander:

1. Setup environment

   ```bash
   pyenv virtualenv 3.14.4 CMC
   pyenv local CMC
   ```

2. Install from source
   
   ```bash
   git clone https://github.com/cloudmesh-ai/cloudmesh-ai-commander.git
   cd cloudmesh-ai-commander
   pip install -e .
   ```

## Core Dependencies
This project depends on the following core components of the Cloudmesh AI ecosystem:
- [cloudmesh-ai-common](https://github.com/cloudmesh-ai/cloudmesh-ai-common)
- [cloudmesh-ai-cmc](https://github.com/cloudmesh-ai/cloudmesh-ai-cmc)
