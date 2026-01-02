import torch
import torch.nn as nn
import torch.nn.functional as F


class SequentialBinaryCNN(nn.Module):
    def __init__(self, vocab_size=256, embedding_dim=64, sequence_length=1024, num_classes=2, 
                 conv_channels=[64, 128, 256], kernel_sizes=[3, 3, 3], use_batch_norm=True):
        super(SequentialBinaryCNN, self).__init__()
        
        # Store configuration
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.sequence_length = sequence_length
        self.num_classes = num_classes
        self.conv_channels = conv_channels
        self.kernel_sizes = kernel_sizes
        self.use_batch_norm = use_batch_norm
        
        # Embedding layer to convert binary input to dense vectors
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        
        # Initialize convolutional layers in a loop
        self.conv_layers = nn.ModuleList()
        self.bn_layers = nn.ModuleList() if use_batch_norm else None
        
        # Create convolutional layers based on the provided configuration
        in_channels = embedding_dim  # Input channels is the embedding dimension
        for i, out_channels in enumerate(conv_channels):
            kernel_size = kernel_sizes[i] if i < len(kernel_sizes) else kernel_sizes[-1]
            
            # Add convolutional layer (using 1D convolutions for sequential data)
            conv_layer = nn.Conv1d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=kernel_size,
                padding=kernel_size // 2,
                stride=1
            )
            self.conv_layers.append(conv_layer)
            
            # Add batch normalization layer if specified
            if use_batch_norm:
                bn_layer = nn.BatchNorm1d(out_channels)
                self.bn_layers.append(bn_layer)
            
            # Update in_channels for the next layer
            in_channels = out_channels
        
        # Calculate the size for the fully connected layer
        # After all convolutions, the sequence length remains the same (due to padding)
        # The number of channels is the last value in conv_channels
        fc_input_size = conv_channels[-1]  # Last channel size
        
        # Global max pooling will reduce sequence length to 1
        # So the input to FC layer is just the number of output channels
        
        # Fully connected layers
        self.fc_layers = nn.ModuleList([
            nn.Linear(fc_input_size, 128),
            nn.Linear(128, num_classes)
        ])
        
        # Dropout layer
        self.dropout = nn.Dropout(0.5)
        
        # Initialize weights in a loop
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize weights using different initialization methods in a loop"""
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                # Initialize convolutional layers
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm1d):
                # Initialize batch norm layers
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                # Initialize linear layers
                nn.init.normal_(m.weight, 0, 0.01)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Embedding):
                # Initialize embedding layer
                nn.init.normal_(m.weight, mean=0, std=0.1)
    
    def forward(self, x):
        # x shape: (batch_size, sequence_length) - containing binary values (0-255 for byte data)
        
        # Apply embedding: (batch_size, sequence_length) -> (batch_size, sequence_length, embedding_dim)
        x = self.embedding(x)
        
        # Transpose to (batch_size, embedding_dim, sequence_length) for Conv1d
        x = x.transpose(1, 2)
        
        # Forward pass through convolutional layers
        for i, conv_layer in enumerate(self.conv_layers):
            x = conv_layer(x)
            
            # Apply batch normalization if available
            if self.bn_layers is not None and i < len(self.bn_layers):
                x = self.bn_layers[i](x)
            
            # Apply activation function
            x = F.gelu(x)  # Using GeLU as requested - often performs better than ReLU
            
            # Apply max pooling after each conv block
            x = F.max_pool1d(x, kernel_size=2, stride=2)
        
        # Apply global max pooling to get a fixed-size representation
        x = F.adaptive_max_pool1d(x, output_size=1)  # (batch_size, channels, 1)
        x = x.squeeze(2)  # (batch_size, channels)
        
        # Forward pass through fully connected layers
        for i, fc_layer in enumerate(self.fc_layers):
            x = fc_layer(x)

            # Apply activation function and dropout for all layers except the last one
            if i < len(self.fc_layers) - 1:  # Don't apply activation after the last layer
                x = F.gelu(x)  # Using GeLU activation between FC layers
                x = self.dropout(x)
        
        return x


def create_model(vocab_size=256, embedding_dim=64, sequence_length=1024, num_classes=2):
    """
    Factory function to create the Sequential Binary CNN model
    """
    # Example configuration - can be modified based on requirements
    conv_channels = [64, 128, 256]
    kernel_sizes = [3, 3, 3]
    
    model = SequentialBinaryCNN(
        vocab_size=vocab_size,
        embedding_dim=embedding_dim,
        sequence_length=sequence_length,
        num_classes=num_classes,
        conv_channels=conv_channels,
        kernel_sizes=kernel_sizes
    )
    return model


if __name__ == "__main__":
    # Example usage with sequential binary data
    model = create_model(vocab_size=256, embedding_dim=64, sequence_length=1024, num_classes=2)
    print(model)
    
    # Test with a dummy input (batch of sequences of binary values)
    # Each sequence contains values from 0-255 representing bytes
    batch_size = 4
    sequence_length = 1024
    dummy_input = torch.randint(0, 256, (batch_size, sequence_length))  # Random bytes
    output = model(dummy_input)
    print(f"Input shape: {dummy_input.shape}")
    print(f"Output shape: {output.shape}")