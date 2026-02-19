#!/bin/zsh

############################################################
## constants
############################################################

CYAN_BOLD="\u001b[36;1m"
YELLOW_BOLD="\u001b[33;1m"
RED_BOLD="\u001b[31;1m"
RESET="\u001b[0m"

############################################################
## parameters
############################################################
EVAL_DIR_ROOT="results"
EXTENDJ_JAVA_VERSION="java11" # matches directory in extendj repo
EXTENDJ_BENCH_JAR_NAME="extendj-bench.jar"

############################################################
## global variables
############################################################
EVAL_DIR="" # we set this value in init

############################################################
## Argument parsing
############################################################

function usage() {
  echo "Usage: $0 -o <outer_iter> -i <inner_iter> [-f]"
  echo ""
  echo "Options:"
  echo "  -o, --outer    Number of outer iterations (default: 10)"
  echo "  -i, --inner    Number of inner iterations (default: 10)"
  echo "  -m, --heap     Java heap size in GB (default: 8)"
  echo "  -p, --projects Path to projects JSON file (default: projects_fast.json)"
  echo "  -h, --help     Show this help message"
  exit "${1:-0}"
}

zparseopts -D -E -F -- \
  o:=flag_outer  -outer:=flag_outer \
  i:=flag_inner  -inner:=flag_inner \
  m:=flag_heap     -heap:=flag_heap \
  p:=flag_projects -projects:=flag_projects \
  h=flag_help    -help=flag_help \
  || usage 1

if (( ${#flag_help} )); then
  usage 0
fi

N_OUTER_ITER="${flag_outer[-1]:-10}"
N_INNER_ITER="${flag_inner[-1]:-10}"
JAVA_HEAP_SIZE="${flag_heap[-1]:-8}"
prj_json="${flag_projects[-1]:-projects_fast.json}"

############################################################
## Utils
############################################################

function log_message() {
  local message="$1"
  local log_type="$2"

  case $log_type in
    info)
      echo -e "\n${CYAN_BOLD}[INFO] ${message}${RESET}"
      ;;
    warning)
      echo -e "${YELLOW_BOLD}[WARNING] ${message}${RESET}"
      ;;
    error)
      echo -e "${RED_BOLD}[WARNING] ${message}${RESET}"
      ;;
    *)
      echo "Invalid log type"
      exit 1
      ;;
  esac
}

function error() {
  log_message $1 "error"
  exit 1
}

############################################################
## Evaluation script steps
############################################################

# init. we begin by creating the directory that we will save the results of this run


function init() {
  TIMESTAMP=$(date +%Y%m%d%H%M%S)
  EVAL_DIR=$EVAL_DIR_ROOT/$TIMESTAMP
  mkdir -p $EVAL_DIR

  jq -n \
    --argjson outer "$N_OUTER_ITER" \
    --argjson inner "$N_INNER_ITER" \
    --argjson heap "$JAVA_HEAP_SIZE" \
    '{outer_iterations: $outer, inner_iterations: $inner, java_heap_size_gb: $heap}' \
    > "$EVAL_DIR/eval_desc.json"

  log_message "saved run parameters to $EVAL_DIR/eval_desc.json" "info"
}

function build() {
  # assert that extendj directory exists in the parent dir of this repo
  local extendj_dir="../../../extendj"

  if [ ! -d "$extendj_dir" ]; then
    log_message "expected location: $extendj_dir" "info"
    error "extendj directory does not exist in the expected location"
  fi

  log_message "building extendj..." "info"

  pushd $extendj_dir
  # TODO, which java version should we build
  ./gradlew --quiet clean ${EXTENDJ_JAVA_VERSION}:bench-jar

  popd

  local jar_path="$extendj_dir/$EXTENDJ_JAVA_VERSION/$EXTENDJ_BENCH_JAR_NAME"

  cp --update=all $jar_path .


  log_message "building extendj: DONE" "info"


  if [ ! -f "$EXTENDJ_BENCH_JAR_NAME" ]; then
    error "jar not coppied!"
  fi

}

function clean() {
  rm $EXTENDJ_BENCH_JAR_NAME
}

function run-eval() {
  log_message "using json $prj_json" "info"
  local enabled_benchmarks
  enabled_benchmarks=$(jq -c '[.benchmarks[] | select(.enable == true)]' $prj_json)
  local count=$(jq 'length' <<< $enabled_benchmarks)

  # for each enabled benchmark
  for ((i = 0; i < $count; i++)); do
    current_benchmark=$(jq -c ".[$i]" <<< $enabled_benchmarks)
    name=$(jq -r '.name' <<< $current_benchmark)
    classpath=$(jq -r '.classpath' <<< $current_benchmark)
    dir_to_analyze=$(jq -r '.dir_to_analyze' <<< $current_benchmark)

    # resolve source files to compile
    local all_files=()
    if [[ "$dir_to_analyze" == "@COMPILE_ARGS" ]]; then
      # read file list from COMPILE_ARGS file
      while IFS= read -r line; do
        all_files+=("$name/$line")
      done < "$name/COMPILE_ARGS"
    else
      # glob for .java files under the specified directory
      all_files=($name/$dir_to_analyze**/*.java(N.))
    fi

    # exclude directories/files specified in the json
    local exclude_dirs=$(jq -r '.exclude_dirs // empty' <<< $current_benchmark)
    if [[ -n "$exclude_dirs" ]]; then
      local n_exclude=$(jq '.exclude_dirs | length' <<< $current_benchmark)
      for ((j = 0; j < $n_exclude; j++)); do
        local exc_path=$(jq -r ".exclude_dirs[$j].path" <<< $current_benchmark)
        local exc_reason=$(jq -r ".exclude_dirs[$j].motivation" <<< $current_benchmark)
        log_message "Excluding '$exc_path' because: $exc_reason" "info"
        # remove matching files from all_files
        all_files=(${all_files:#$name/$exc_path*})
      done
    fi

    log_message "evaluating $name with $N_OUTER_ITER outer iterations (${#all_files[@]} source files)..." "info"

    # for $N_OUTER_ITER times we now run the benchmark
    for ((iter = 1; iter <= $N_OUTER_ITER; iter++)); do
      java -Xmx${JAVA_HEAP_SIZE}g -jar ./$EXTENDJ_BENCH_JAR_NAME \
        $N_INNER_ITER \
        -classpath "$classpath" \
        ${all_files[@]}
    done
  done
}

############################################################
## run the evaluation
############################################################

log_message "running evaluation: n_outer=$N_OUTER_ITER, n_inner=$N_INNER_ITER, heap_size=$JAVA_HEAP_SIZE, project_json=$prj_json" "info"

# init
# build
# run-eval
# clean
