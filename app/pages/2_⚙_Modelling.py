import streamlit as st
import pandas as pd
import os
import json
import time
from typing import List
from sklearn.model_selection import train_test_split
from app.core.system import AutoMLSystem
from autoop.core.ml.dataset import Dataset
from autoop.core.ml.feature import Feature
from autoop.core.ml.pipeline import Pipeline
from autoop.core.ml.model import Model
from autoop.core.ml.metric import Metric
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    mean_squared_error,
    mean_absolute_error,
    r2_score,
)
import pickle

# Set page configuration
st.set_page_config(page_title="Modelling", page_icon="📈")

# Directory for saving pipelines
PIPELINES_DIR = os.path.join('assets', 'pipelines')
os.makedirs(PIPELINES_DIR, exist_ok=True)

# Load datasets from the registry
def load_registry():
    ASSETS_DIR = 'assets'
    REGISTRY_FILE = os.path.join(ASSETS_DIR, 'registry.json')
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)
    return []

registry = load_registry()
datasets = [entry for entry in registry if entry['type'] == 'dataset']

# Display page
st.write("# ⚙ Modelling")
st.write("In this section, you can design a machine learning pipeline to train a model on a dataset.")

if datasets:
    st.subheader("Select Dataset")
    dataset_options = [dataset['name'] for dataset in datasets]
    selected_dataset_name = st.selectbox("Select a dataset", dataset_options)

    selected_dataset_info = next((ds for ds in datasets if ds['name'] == selected_dataset_name), None)
    if selected_dataset_info:
        dataset_path = os.path.join('assets', selected_dataset_info['asset_path'])
        df = pd.read_csv(dataset_path)
        
        # Check for missing values
        if df.isnull().values.any():
            st.error("Dataset contains missing values. Please provide a dataset with no NaN or missing values.")
            st.stop()

        # Check for categorical and numerical features only
        allowed_dtypes = ['int64', 'float64', 'object']
        if not all(dtype in allowed_dtypes for dtype in df.dtypes):
            st.error("Dataset contains unsupported data types. Only categorical and numerical features are allowed.")
            st.stop()
        
        st.write("Preview of selected dataset:")
        st.dataframe(df.head())

        # Detect features
        features = [Feature(name=col, type='numerical' if df[col].dtype in ['int64', 'float64'] else 'categorical') for col in df.columns]
        feature_names = [feature.name for feature in features]

        st.subheader("Select Features")
        input_features = st.multiselect("Select input features", feature_names)
        target_feature = st.selectbox("Select target feature", feature_names)

        # Manual feature selection: Check that the user selected features manually
        if not input_features or not target_feature:
            st.error("Please select input and target features manually.")
            st.stop()

        # Determine task type based on target feature type
        task_type = 'classification' if df[target_feature].dtype == 'object' else 'regression'
        st.write(f"Detected task type: **{task_type.capitalize()}**")

        # Model selection
        st.subheader("Select Model")
        model_options = {
            'classification': {
                'Logistic Regression': LogisticRegression,
                'Decision Tree Classifier': DecisionTreeClassifier,
                'Random Forest Classifier': RandomForestClassifier
            },
            'regression': {
                'Linear Regression': LinearRegression,
                'Ridge Regression': Ridge,
                'Decision Tree Regressor': DecisionTreeRegressor
            }
        }
        selected_model_name = st.selectbox("Select a model", list(model_options[task_type].keys()))
        selected_model_class = model_options[task_type][selected_model_name]

        # Dataset split
        st.subheader("Select Dataset Split")
        split_ratio = st.slider("Select train/test split ratio", min_value=0.1, max_value=0.9, value=0.8)

        # Evaluation metrics
        st.subheader("Select Evaluation Metrics")
        metrics = {
            'classification': {
                'Accuracy': accuracy_score,
                'Precision': precision_score,
                'Recall': recall_score,
                'F1 Score': f1_score
            },
            'regression': {
                'Mean Squared Error': mean_squared_error,
                'Mean Absolute Error': mean_absolute_error,
                'R2 Score': r2_score
            }
        }
        selected_metrics = st.multiselect("Select evaluation metrics", list(metrics[task_type].keys()))
        selected_metric_functions = [metrics[task_type][metric] for metric in selected_metrics]

        # Pipeline name and version
        st.subheader("Save Pipeline")
        pipeline_name = st.text_input("Pipeline Name")
        pipeline_version = st.text_input("Pipeline Version")

        # Run pipeline button
        if st.button("Run and Save Pipeline") and pipeline_name and pipeline_version:
            st.write("Training the model...")
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Train/test split
            X_train, X_test, y_train, y_test = train_test_split(df[input_features], df[target_feature], test_size=(1 - split_ratio), random_state=42)
            model = selected_model_class()
            
            for i in range(1, 101):
                time.sleep(0.02)
                progress_bar.progress(i / 100)
                status_text.text(f"Training Progress: {i}%")
            
            model.fit(X_train, y_train)
            st.write("Training Complete!")
            
            # Evaluate and display metrics
            st.write("**Pipeline Results:**")
            results = {}
            for metric_func in selected_metric_functions:
                train_metric = metric_func(y_train, model.predict(X_train))
                test_metric = metric_func(y_test, model.predict(X_test))
                metric_name = metric_func.__name__.replace("_", " ").title()
                st.write(f"{metric_name} (Train): {train_metric}")
                st.write(f"{metric_name} (Test): {test_metric}")
                results[metric_name] = {"train": train_metric, "test": test_metric}

            # Save the pipeline metadata
            pipeline_data = {
                "pipeline_name": pipeline_name,
                "pipeline_version": pipeline_version,
                "model_type": task_type,
                "model_name": selected_model_name,
                "input_features": input_features,
                "target_feature": target_feature,
                "split_ratio": split_ratio,
                "metrics": results
            }
            pipeline_path = os.path.join(PIPELINES_DIR, f"{pipeline_name}_{pipeline_version}.json")
            
            with open(pipeline_path, 'w') as f:
                json.dump(pipeline_data, f, indent=4)

            # Save the trained model as a .pkl file
            model_file_path = os.path.join(PIPELINES_DIR, f"{pipeline_name}_{pipeline_version}_model.pkl")
            with open(model_file_path, 'wb') as model_file:
                pickle.dump(model, model_file)

            st.success(f"Pipeline '{pipeline_name}' (version {pipeline_version}) has been saved successfully.")
else:
    st.write("No datasets available. Please upload a dataset to start modeling.")
