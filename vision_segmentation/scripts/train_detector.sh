#!/bin/bash
#SBATCH --job-name=fracture_det
#SBATCH --output=/d/hpc/home/st5804/wilhelm/logs/train_%j.out
#SBATCH --error=/d/hpc/home/st5804/wilhelm/logs/train_%j.err
#SBATCH --time=4:00:00
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G

module load Anaconda3/2023.07-2

source $(conda info --base)/etc/profile.d/conda.sh

conda activate masters
cd /d/hpc/home/st5804/wilhelm/vision_segmentation/scripts

pip install -r ../requirements.txt --quiet
pip install ultralytics pyyaml --quiet

echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "Python: $(which python)"

python train_detector.py
