from typing import List
import pickle

from autoop.core.ml.artifact import Artifact
from autoop.core.ml.dataset import Dataset
from autoop.core.ml.model import Model
from autoop.core.ml.feature import Feature
from autoop.core.ml.metric import Metric
from autoop.functional.preprocessing import preprocess_features
import numpy as np


class Pipeline:
    """A class representing a machine learning pipeline."""
    def __init__(self,
                 metrics: List[Metric],
                 dataset: Dataset,
                 model: Model,
                 input_features: List[Feature],
                 target_f: Feature,
                 split=0.8) -> None:
        """Initialize the pipeline."""
        self._dataset = dataset
        self._model = model
        self._input_features = input_features
        self._target_feature = target_f
        self._metrics = metrics
        self._artifacts = {}
        self._split = split
        if (
            target_f.type == "categorical" and model.type != "classification"
        ):
            raise ValueError(
                "Model type must be classification \
for categorical target feature")
        if (
            target_f.type == "continuous" and model.type != "regression"
        ):
            raise ValueError(
                "Model type must be regression \
for continuous target feature")

    def __str__(self) -> str:
        """Return a string representation of the pipeline."""
        return f"""
Pipeline(
    model={self._model.type},
    input_features={list(map(str, self._input_features))},
    target_feature={str(self._target_feature)},
    split={self._split},
    metrics={list(map(str, self._metrics))},
)
"""

    @property
    def model(self) -> Model:
        """Used to get the model used in the pipeline."""
        return self._model

    @property
    def artifacts(self) -> List[Artifact]:
        """Used to get the artifacts generated during \
the pipeline execution to be saved."""
        artifacts = []
        for name, artifact in self._artifacts.items():
            artifact_type = artifact.get("type")
            if artifact_type in ["OneHotEncoder"]:
                data = artifact["encoder"]
                data = pickle.dumps(data)
                artifacts.append(Artifact(name=name, data=data))
            if artifact_type in ["StandardScaler"]:
                data = artifact["scaler"]
                data = pickle.dumps(data)
                artifacts.append(Artifact(name=name, data=data))

        pipeline_data = {
            "input_features": self._input_features,
            "target_feature": self._target_feature,
            "split": self._split,
        }
        artifacts.append(
            Artifact(name="pipeline_config", data=pickle.dumps(pipeline_data))
        )
        artifacts.append(
            self._model.to_artifact(name=f"pipeline_model_{self._model.type}")
        )

        return artifacts

    def _register_artifact(self, name: str, artifact) -> None:
        """Register an artifact generated during the pipeline execution."""
        self._artifacts[name] = artifact

    def _preprocess_features(self) -> None:
        """Preprocess the input and target features."""
        (target_feature_name, target_data, artifact) = preprocess_features(
            [self._target_feature], self._dataset
        )[0]
        self._register_artifact(target_feature_name, artifact)
        input_results = preprocess_features(
            self._input_features, self._dataset
        )
        for (feature_name, data, artifact) in input_results:
            self._register_artifact(feature_name, artifact)
        # Get the input vectors and output vector,
        # sort by feature name for consistency
        self._output_vector = target_data
        self._input_vectors = [
            data for (feature_name, data, artifact) in input_results
        ]

    def _split_data(self) -> None:
        """Split the data into training and testing sets."""
        # Split the data into training and testing sets
        split = self._split
        self._train_X = [
            vector[:int(split * len(vector))] for vector in self._input_vectors
        ]
        self._test_X = [
            vector[int(split * len(vector)):] for vector in self._input_vectors
        ]
        self._train_y = self._output_vector[
            :int(split * len(self._output_vector))
        ]
        self._test_y = self._output_vector[
            int(split * len(self._output_vector)):
        ]

    def _compact_vectors(self, vectors: List[np.array]) -> np.array:
        """Combine the input vectors into a single matrix."""
        return np.concatenate(vectors, axis=1)

    def _train(self) -> None:
        """Train the model on the training data."""
        X = self._compact_vectors(self._train_X)
        Y = self._train_y
        self._model.fit(X, Y)

    def _evaluate(self) -> None:
        """Evaluate the model on the test data."""
        X = self._compact_vectors(self._test_X)
        Y = self._test_y
        self._metrics_results = []
        predictions = self._model.predict(X)
        for metric in self._metrics:
            result = metric.evaluate(predictions, Y)
            self._metrics_results.append((metric, result))
        self._predictions = predictions

    def execute(self) -> dict:
        """Execute the pipeline."""
        self._preprocess_features()
        self._split_data()
        self._train()

        # Evaluate on training set
        train_X = self._compact_vectors(self._train_X)
        train_Y = self._train_y
        train_predictions = self._model.predict(train_X)
        train_metrics_results = [
            (
                metric, metric.evaluate(train_predictions, train_Y)
            ) for metric in self._metrics
        ]

        # Evaluate on test (evaluation) set
        test_X = self._compact_vectors(self._test_X)
        test_Y = self._test_y
        test_predictions = self._model.predict(test_X)
        test_metrics_results = [
            (
                metric, metric.evaluate(test_predictions, test_Y)
            ) for metric in self._metrics
        ]

        # Return both training and test metrics
        return {
            "train_metrics": train_metrics_results,
            "test_metrics": test_metrics_results,
            "train_predictions": train_predictions,
            "test_predictions": test_predictions,
        }

    def save_pipeline(self, name: str, version: str) -> Artifact:
        """Converts the pipeline into an artifact and allows it to be saved."""
        pipeline_artifact = {
            "name": name,
            "version": version,
            "pipeline_data": self.artifacts
        }
        artifact_data = pickle.dumps(pipeline_artifact)
        artifact = Artifact(name=f"{name}_v{version}", data=artifact_data)
        return artifact
