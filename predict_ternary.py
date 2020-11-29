# Predict, then uncollate
import argparse
import json
import os
import shutil
import subprocess
from typing import Any, Dict
import sys
from dygie_visualize_util import Dataset
import pathlib
from pathlib import Path
from dygie.data.dataset_readers import document
import pandas as pd
from decode import decode
import re
import traceback
"""
Usage
python predict_ternary.py --data_path data/cofie --device 0,1,2,3 --serial_dir models/cofie-t/collated 
python predict_ternary.py --data_path data/cofie --device 0,1,2,3 --serial_dir models/cofie-t/collated  --pred_dir predictions/cofie-t
"""

"""
python predict_ternary.py --data_dir predictions/oa_extrated_0 --device 0 --serial_dir pretrained/ternary-model.tar.gz  --pred_dir predictions/final_pred_0/
python predict_ternary.py --data_dir predictions/oa_extrated_1 --device 1 --serial_dir pretrained/ternary-model.tar.gz  --pred_dir predictions/final_pred_1/
"""


"""
test:
python predict_ternary.py --data_dir data/ergothioneine_REed --device 0 --serial_dir pretrained/ternary-model.tar.gz  --pred_dir predictions/final_pred_0/
"""


def stringify(xs):
    return " ".join(xs)

def format_predicted_events(sent, doc_key=""):
    res = []
    for event in sent.predicted_events:
        if len(event.arguments) < 2:
          continue
        arg0 = event.arguments[0]
        arg1 = event.arguments[1]

        entry = {"doc_key": doc_key,
                 "sentence": stringify(sent.text),
                 "arg0": stringify(arg0.span.text),
                 "trigger": event.trigger.token.text,
                 "arg1": stringify(arg1.span.text),
                 "arg0_logit": arg0.raw_score,
                 "trigger_logit": event.trigger.raw_score,
                 "arg1_logit": arg1.raw_score,
                 "arg0_softmax": arg0.softmax_score,
                 "trigger_softmax": event.trigger.softmax_score,
                 "arg1_softmax": arg1.softmax_score}
        res.append(entry)
    return res


def format_dataset(dataset):
    predicted_events = []

    for doc in dataset:
        for sent in doc:
            predicted = format_predicted_events(sent, doc.doc_key)
            predicted_events.extend(predicted)

    predicted_events = pd.DataFrame(predicted_events)

    return predicted_events

def load_jsonl(fname):
    return [json.loads(x) for x in open(fname)]


def save_jsonl(xs, fname):
    with open(fname, "w") as f:
        for x in xs:
            print(json.dumps(x), file=f)

if __name__ == '__main__':
    parser = argparse.ArgumentParser() 

    parser.add_argument('--serial_dir',
                        type=str,
                        help="path to the saved trained model",
                        default="./models/events/")

    parser.add_argument('--data_dir', 
                        type=str,
                        help="path to the directory containing the test and dev data files",
                        default="data/processed/collated/")


    parser.add_argument('--test_file',
                            type=str,
                            help="Please mention test filename in the data_path if test filename is not test.json",
                            required=False,
                            default="test.json")

    parser.add_argument('--device',
                        type=str,
                        default='0',
                        required=False,
                        help="cuda devices comma seperated")


    parser.add_argument('--pred_dir',
                            type=str,
                            help="Path to the directory to save the prediction. default is ./predictions/",
                            required=False,
                            default="./predictions/")

    parser.add_argument('--pred_file',
                            type=str,
                            help="Please mention prediction filename(including json extention) in the pred_dir if prediction filename should not be pred.json / pred.tsv",
                            required=False,
                            default="pred.json")

    parser.add_argument('--decode_file',
                            type=str,
                            help="Please mention prediction decode filename(including json extention) in the pred_dir if prediction filename should not be decode.json",
                            required=False,
                            default="decode.json")



    args = parser.parse_args()
    data_root = pathlib.Path(args.data_dir) 
    serial_dir = pathlib.Path(args.serial_dir)
    pred_dir = pathlib.Path(args.pred_dir)

    
    pred_dir.mkdir(parents=True, exist_ok=True)
    test_dir = data_root / args.test_file   
        
        
    uncollated_pred_path = pred_dir/ "pred.json"
    uncollated_pred_path_decode = pred_dir/ "decode.json"
    uncollated_pred_path_tsv = pred_dir/ "pred.tsv"
    # print(f"\'{args.device}\'")
    # exit()
    # args.device = str([0, 1])
    idx = 0

    for data_f in os.listdir(args.data_dir):
        try:
            if data_f.endswith("jsonl") or data_f == "test.json":   # TODO: delete the second condition
                idx = re.search(r'\d+', data_f).group(0)
                if f"decode_{idx}.json" in os.listdir(pred_dir):
                    continue
                test_dir = data_root / data_f
                uncollated_pred_path = pred_dir / f"pred_{idx}.json"
                uncollated_pred_path_decode = pred_dir / f"decode_{idx}.json"
                uncollated_pred_path_tsv = pred_dir / f"pred_{idx}.tsv"
                allennlp_command = [
                          "allennlp",
                          "predict",
                          str(serial_dir),
                          str(test_dir),
                          "--predictor dygie",
                          "--include-package dygie",
                          "--use-dataset-reader",
                          "--output-file",
                          str(uncollated_pred_path),
                          "--cuda-device",
                          args.device
                          # f"\"{args.device}\""
                  ]
                # subprocess.run(" ".join(allennlp_command), shell=True, check=True)
                subprocess.call(" ".join(allennlp_command), shell=True)

                in_data = load_jsonl(str(uncollated_pred_path))
                out_data = decode(in_data)
                save_jsonl(out_data, str(uncollated_pred_path_decode))
                dataset = document.Dataset.from_jsonl(str(uncollated_pred_path_decode))
                pred = format_dataset(dataset)
                pred.to_csv(str(uncollated_pred_path_tsv), sep="\t", float_format="%0.4f", index=False)
        except Exception as e:
            with open("predict_ternary_err.log" , "a") as f:
                f.write(data_f + "\n")
            pass
