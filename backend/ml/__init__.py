"""ML package: training, inference, and feature-importance tooling."""

from backend.ml.drift_detection import DriftDetector, DriftReport
from backend.ml.explainability import ExplainabilityEngine, ExplanationResult
from backend.ml.feature_importance_tracker import (
    FeatureImportanceResult,
    FeatureImportanceTracker,
)
from backend.ml.inference import InferenceEngine, Inferencer, PredictionLogger
from backend.ml.model_manager import DeploymentMode, ManagedModel, ModelManager
from backend.ml.prediction_tracker import get_prediction_tracker
from backend.ml.retraining import RetrainingDecision, RetrainingPipeline, ValidationDecision
from backend.ml.trainer import (
    CollectedTrainingData,
    FeatureEngineeringResult,
    FeatureSelectionResult,
    HyperparameterOptimizationResult,
    TrainedModelArtifact,
    TrainingPipeline,
    train_all_horizons,
    train_model,
)
from backend.ml.training_pipeline import MLTrainingPipeline, TrainingOutput

__all__ = [
    "FeatureImportanceResult",
    "FeatureImportanceTracker",
    "DriftDetector",
    "DriftReport",
    "ExplainabilityEngine",
    "ExplanationResult",
    "MLTrainingPipeline",
    "TrainingOutput",
    "InferenceEngine",
    "Inferencer",
    "PredictionLogger",
    "RetrainingDecision",
    "RetrainingPipeline",
    "ValidationDecision",
    "DeploymentMode",
    "ManagedModel",
    "ModelManager",
    "CollectedTrainingData",
    "FeatureEngineeringResult",
    "FeatureSelectionResult",
    "HyperparameterOptimizationResult",
    "TrainedModelArtifact",
    "TrainingPipeline",
    "get_prediction_tracker",
    "train_all_horizons",
    "train_model",
]
