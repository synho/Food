import json
import glob
import os

def consolidate_graph():
    input_dir = "data/extracted_triples"
    output_file = os.path.join(input_dir, "master_graph.json")
    
    all_triples = []
    
    # Find all triple files except the master itself
    triple_files = glob.glob(os.path.join(input_dir, "*_triples.json"))
    
    for file_path in triple_files:
        with open(file_path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                all_triples.extend(data)
                
    with open(output_file, "w") as f:
        json.dump(all_triples, f, indent=4)
        
    print(f"Consolidated {len(all_triples)} triples from {len(triple_files)} files into {output_file}")

if __name__ == "__main__":
    consolidate_graph()
