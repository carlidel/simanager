if [ -z "$SIMPATH" ]; then
    SIMPATH=$(pwd)
fi

python script.py --yaml_path "$SIMPATH/params.yaml"