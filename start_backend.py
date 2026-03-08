"""Start backend without auto-prediction for UI testing."""
import uvicorn
from backend.app.main import create_app, AppConfig

# Create app with prediction disabled
config = AppConfig(
    enable_binance_stream=True,
    enable_prediction_autostart=False,  # Disable to avoid model artifact requirement
    enable_coinpaprika_metrics=False,
)

app = create_app(config)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
