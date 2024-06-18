if [ -z "$WORKDIR" ]; then
    WORKDIR=$(pwd)
fi

python $WORKDIR/script.py --yaml_path "$WORKDIR/params.yaml"