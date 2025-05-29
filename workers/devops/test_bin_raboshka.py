#!/usr/bin/env python3
import argparse
import os
import sys
import cloudpickle
import tempfile
import subprocess
import logging
import pprint
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("raboshka_tester")

def parse_args():
    parser = argparse.ArgumentParser(description="Test a compiled raboshka worker")
    parser.add_argument(
        "worker_name",
        help="Name of the compiled worker executable in bin/raboshka directory"
    )
    parser.add_argument(
        "--test-func",
        choices=["standard", "numpy", "torch", "all"],
        default="all",
        help="Type of test function to run (default: all)"
    )
    return parser.parse_args()

def get_worker_path(worker_name):
    """Get the full path to the worker executable"""
    script_dir = Path(__file__).resolve().parent
    apps_root = script_dir.parent
    bin_dir = apps_root / "bin" / "raboshka"
    
    # If worker_name already includes the full path
    worker_path = Path(worker_name)
    if worker_path.is_absolute():
        return worker_path
    
    # Check if worker_name is in the bin/raboshka directory
    worker_path = bin_dir / worker_name
    if worker_path.exists():
        return worker_path
    
    # Check if worker_name exists in current directory
    worker_path = Path.cwd() / worker_name
    if worker_path.exists():
        return worker_path
    
    raise FileNotFoundError(f"Worker executable not found: {worker_name}")

def create_standard_test():
    """Create a test function using only standard library modules"""
    def test_standard(kwargs):
        import math
        import datetime
        import json
        import random
        import hashlib
        
        # Get parameters
        seed = kwargs.get("seed", 42)
        iterations = kwargs.get("iterations", 10)
        
        # Set random seed
        random.seed(seed)
        
        # Generate some random data and perform calculations
        numbers = [random.random() * 100 for _ in range(iterations)]
        result = {
            "numbers": numbers,
            "sum": sum(numbers),
            "average": sum(numbers) / len(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "sqrt_sum": math.sqrt(sum(numbers)),
            "current_time": str(datetime.datetime.now()),
            "md5_hash": hashlib.md5(json.dumps(numbers).encode()).hexdigest()
        }
        
        return result
    
    return {
        "func": test_standard,
        "kwargs": {"seed": 12345, "iterations": 15}
    }

def create_numpy_test():
    """Create a test function that uses numpy"""
    def test_numpy(kwargs):
        import numpy as np
        
        # Get parameters
        seed = kwargs.get("seed", 42)
        size = kwargs.get("size", 1000)
        
        # Set seed
        np.random.seed(seed)
        
        # Create arrays and perform operations
        arr1 = np.random.rand(size)
        arr2 = np.random.rand(size)
        
        # Matrix operations
        matrix1 = np.random.rand(10, 10)
        matrix2 = np.random.rand(10, 10)
        
        result = {
            "arr1_mean": float(np.mean(arr1)),
            "arr2_std": float(np.std(arr2)),
            "correlation": float(np.corrcoef(arr1, arr2)[0, 1]),
            "dot_product": float(np.dot(arr1[:5], arr2[:5])),
            "matrix_det": float(np.linalg.det(matrix1)),
            "matrix_mult": np.matmul(matrix1[:2, :2], matrix2[:2, :2]).tolist(),
            "fft_sample": np.fft.fft(arr1[:10]).real.tolist(),
            "stats": {
                "percentile_25": float(np.percentile(arr1, 25)),
                "percentile_50": float(np.percentile(arr1, 50)),
                "percentile_75": float(np.percentile(arr1, 75))
            }
        }
        return result
    
    return {
        "func": test_numpy,
        "kwargs": {"seed": 12345, "size": 500}
    }

def create_torch_test():
    """Create a test function that trains a simple image classification model with PyTorch"""
    def test_torch(kwargs):
        import torch
        import torch.nn as nn
        import torch.optim as optim
        import torchvision
        import torchvision.transforms as transforms
        import numpy as np
        
        # Parameters
        batch_size = kwargs.get("batch_size", 4)
        num_epochs = kwargs.get("num_epochs", 2)
        learning_rate = kwargs.get("learning_rate", 0.001)
        
        # Set random seed for reproducibility
        torch.manual_seed(12345)
        np.random.seed(12345)
        
        # Simple CNN model
        class SimpleCNN(nn.Module):
            def __init__(self):
                super(SimpleCNN, self).__init__()
                self.conv1 = nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1)
                self.relu = nn.ReLU()
                self.maxpool = nn.MaxPool2d(kernel_size=2)
                self.fc = nn.Linear(16 * 14 * 14, 10)
                
            def forward(self, x):
                x = self.conv1(x)
                x = self.relu(x)
                x = self.maxpool(x)
                x = x.view(x.size(0), -1)
                x = self.fc(x)
                return x
        
        # Generate a small synthetic dataset (since we don't want to download MNIST)
        def generate_synthetic_data(n_samples=100):
            # Create random images (1 channel, 28x28 pixels)
            images = torch.randn(n_samples, 1, 28, 28)
            # Create random labels (0-9)
            labels = torch.randint(0, 10, (n_samples,))
            return images, labels

        # Generate synthetic training and test data
        train_images, train_labels = generate_synthetic_data(n_samples=batch_size * 10)
        test_images, test_labels = generate_synthetic_data(n_samples=batch_size * 5)
        
        # Create data loaders
        train_dataset = torch.utils.data.TensorDataset(train_images, train_labels)
        test_dataset = torch.utils.data.TensorDataset(test_images, test_labels)
        
        train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        
        # Initialize the model, loss function and optimizer
        model = SimpleCNN()
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        
        # Training metrics
        training_loss = []
        
        # Training loop
        for epoch in range(num_epochs):
            running_loss = 0.0
            for i, (inputs, labels) in enumerate(train_loader):
                # Zero the parameter gradients
                optimizer.zero_grad()
                
                # Forward pass
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                # Backward pass and optimize
                loss.backward()
                optimizer.step()
                
                running_loss += loss.item()
            
            epoch_loss = running_loss / len(train_loader)
            training_loss.append(epoch_loss)
            
        # Evaluation
        model.eval()
        correct = 0
        total = 0
        
        with torch.no_grad():
            for inputs, labels in test_loader:
                outputs = model(inputs)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        
        accuracy = 100 * correct / total
        
        # Sample forward pass
        sample_input = test_images[:1]
        sample_output = model(sample_input).detach().numpy()
        
        # Return results
        result = {
            "epochs": num_epochs,
            "batch_size": batch_size,
            "final_training_loss": training_loss[-1],
            "training_loss_history": training_loss,
            "test_accuracy": accuracy,
            "model_state_size_bytes": sum(p.numel() * p.element_size() for p in model.parameters()),
            "sample_prediction": sample_output.tolist()[0],
            "sample_prediction_class": int(np.argmax(sample_output))
        }
        
        return result
    
    return {
        "func": test_torch,
        "kwargs": {"batch_size": 4, "num_epochs": 2, "learning_rate": 0.001}
    }

def run_test(worker_path, call_spec):
    """Run a test on the worker"""
    with tempfile.NamedTemporaryFile(delete=False) as call_spec_file:
        call_spec_path = call_spec_file.name
        cloudpickle.dump(call_spec, call_spec_file)
    
    with tempfile.NamedTemporaryFile(delete=False) as returned_file:
        returned_path = returned_file.name
        
    # Call the worker executable
    cmd = [str(worker_path), call_spec_path, returned_path]
    logger.info(f"Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Worker stdout: {result.stdout}")
        
        if result.stderr:
            logger.warning(f"Worker stderr: {result.stderr}")
        
        # Load the returned result
        with open(returned_path, "rb") as f:
            returned = cloudpickle.load(f)
        
        if isinstance(returned, Exception):
            logger.error(f"Worker returned exception: {returned}")
            if hasattr(returned, 'raboshka_traceback'):
                logger.error(f"Traceback: {returned.raboshka_traceback}")
            return False, None
        
        return True, returned
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Worker execution failed with code {e.returncode}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        return False, None
    
    except Exception as e:
        logger.error(f"Error running test: {e}")
        return False, None
    
    finally:
        # Clean up temporary files
        for path in [call_spec_path, returned_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Error cleaning up {path}: {e}")

def main():
    args = parse_args()
    
    try:
        worker_path = get_worker_path(args.worker_name)
        logger.info(f"Testing worker: {worker_path}")
        
        test_functions = {
            "standard": create_standard_test,
            "numpy": create_numpy_test,
            "torch": create_torch_test
        }
        
        if args.test_func == "all":
            tests_to_run = list(test_functions.keys())
        else:
            tests_to_run = [args.test_func]
        
        all_passed = True
        
        for test_name in tests_to_run:
            logger.info(f"Running {test_name} test...")
            call_spec = test_functions[test_name]()
            success, result = run_test(worker_path, call_spec)
            
            if success:
                logger.info(f"{test_name} test PASSED!")
                logger.info("Result:")
                pprint.pprint(result)
            else:
                logger.error(f"{test_name} test FAILED!")
                all_passed = False
        
        if all_passed:
            logger.info("All tests PASSED!")
            return 0
        else:
            logger.error("Some tests FAILED!")
            return 1
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
