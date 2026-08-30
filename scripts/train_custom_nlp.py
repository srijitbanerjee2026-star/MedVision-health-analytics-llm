import os
import joblib
import torch
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification, 
    Trainer, 
    TrainingArguments
)

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("user67", "")
MYSQL_DB = os.getenv("MYSQL_DB", "medvision")

DISTILBERT_PATH = os.getenv("DISTILBERT_PATH", "./medvision_distilbert")
ENCODER_PATH = os.getenv("ENCODER_PATH", "./disease_label_encoder.pkl")

class ClinicalDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def train_from_mysql():
    db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    engine = create_engine(db_url)

    query = "SELECT chief_complaint, diagnosis FROM triage_records WHERE chief_complaint IS NOT NULL"
    df = pd.read_sql(query, con=engine)

    label_encoder = LabelEncoder()
    df["encoded_label"] = label_encoder.fit_transform(df["diagnosis"])
    joblib.dump(label_encoder, ENCODER_PATH)

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        df["chief_complaint"].tolist(),
        df["encoded_label"].tolist(),
        test_size=0.2,
        random_state=42
    )

    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=128)
    val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=128)

    train_dataset = ClinicalDataset(train_encodings, train_labels)
    val_dataset = ClinicalDataset(val_encodings, val_labels)

    num_labels = len(label_encoder.classes_)
    model = AutoModelForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=num_labels
    )

    training_args = TrainingArguments(
        output_dir="./results",
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir="./logs",
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset
    )

    trainer.train()
    model.save_pretrained(DISTILBERT_PATH)
    tokenizer.save_pretrained(DISTILBERT_PATH)

if __name__ == "__main__":
    train_from_mysql()