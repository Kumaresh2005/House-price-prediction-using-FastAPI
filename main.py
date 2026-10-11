
import io
import joblib
import pandas as pd

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="California House Price Prediction API",
    description="Predict house values using a trained Random Forest model",
    version="1.0.0"
)

# Load model and feature names
Model = joblib.load("house_model.joblib")
features = joblib.load("house_features.joblib")

# Required input columns
required_columns = [
    "MedInc",
    "HouseAge",
    "AveRooms",
    "AveBedrms",
    "Population",
    "AveOccup",
    "Latitude",
    "Longitude"
]


# Input schema
class HouseFeatures(BaseModel):
    MedInc: float = Field(gt=0, description="Median income in the area")
    HouseAge: float = Field(ge=0, description="Median house age")
    AveRooms: float = Field(gt=0, description="Average number of rooms")
    AveBedrms: float = Field(gt=0, description="Average number of bedrooms")
    Population: float = Field(gt=0, description="Total population")
    AveOccup: float = Field(gt=0, description="Average household occupancy")
    Latitude: float = Field(ge=32, le=42, description="Latitude")
    Longitude: float = Field(ge=-125, le=-114, description="Longitude")


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "California House Prediction API",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "single_prediction": "/predict",
            "csv_prediction": "/predict-file",
            "documentation": "/docs"
        }
    }


# Health endpoint
@app.get("/health")
def health():
    return {
        "status": "running",
        "model": type(Model).__name__,
        "features": features,
        "dataset": "California Housing"
    }


# Single-house prediction
@app.post("/predict")
def predict(house: HouseFeatures):
    try:
        input_data = pd.DataFrame([{
            "MedInc": house.MedInc,
            "HouseAge": house.HouseAge,
            "AveRooms": house.AveRooms,
            "AveBedrms": house.AveBedrms,
            "Population": house.Population,
            "AveOccup": house.AveOccup,
            "Latitude": house.Latitude,
            "Longitude": house.Longitude
        }])

        # Match the training feature order
        input_data = input_data[features]

        predicted = float(Model.predict(input_data)[0])
        price_usd = predicted * 100000

        return {
            "success": True,
            "predicted_price": f"${price_usd:,.0f}",
            "predicted_price_units": round(predicted, 4),
            "currency": "USD"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


# CSV file prediction
@app.post("/predict-file")
async def predict_file(file: UploadFile = File(...)):

    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file only"
        )

    # Read uploaded CSV
    contents = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read CSV. Please upload a valid CSV file."
        )
    finally:
        await file.close()

    # Check for empty file
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CSV has no data rows"
        )

    # Check required columns
    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_columns}"
        )

    try:
        # Select columns in training order
        input_data = df[features].copy()

        # Convert values to numeric
        for col in features:
            input_data[col] = pd.to_numeric(
                input_data[col], errors="raise"
            )

        # Check for invalid numeric values
        if input_data.isnull().any().any():
            raise HTTPException(
                status_code=400,
                detail="CSV contains missing values in feature columns"
            )

        if not input_data.map(
            lambda value: pd.notna(value) and abs(value) != float("inf")
        ).all().all():
            raise HTTPException(
                status_code=400,
                detail="CSV contains infinite or invalid numeric values"
            )

        # Predict all house values
        predictiions = Model.predict(input_data)

        # Convert model output to USD
        df["Predicted_columns_usd"] = [
            f"${float(value) * 100000:,.0f}"
            for value in predictiions
        ]

        # Convert DataFrame to CSV text
        output = df.to_csv(index=False)

        # Return downloadable CSV
        return StreamingResponse(
            io.StringIO(output),
            media_type="text/csv",
            headers={
                "Content-Disposition":
                    "attachment; filename=predictions.csv"
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )
