
from sklearn.datasets import fetch_california_housing
import pandas as pd

# Load the dataset
data = fetch_california_housing()

# Create a DataFrame
df = pd.DataFrame(data.data, columns=data.feature_names)

# Add target column
df["Price"] = data.target

# Display dataset information
print("Shape:", df.shape)

print("\nFirst 5 rows:")
print(df.head())

print("\nStatistical summary:")
print(df.describe())
