#!/bin/zsh

# escape sequences for formated output
CYAN_BOLD="\u001b[36;1m"
YELLOW_BOLD="\u001b[33;1m"
RED_BOLD="\u001b[31;1m"
RESET="\u001b[0m"

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

# parameters
EVAL_DIR_ROOT="results"
EXTENDJ_JAVA_VERSION="java11" # matches directory in extendj repo
EXTENDJ_BENCH_JAR_NAME="extendj-bench.jar"

# global variables
EVAL_DIR=""

#arguments
N_OUTER_ITER="$1"
N_INNER_ITER="$2"
if [ "$3" = "fast" ]; then
  log_message "Running in fast mode. Meaning that a smaller number of iterations will be run on one single project." "info"
  FAST=true
else
  FAST=false
fi

if [ "$FAST" = true ]; then
  prj_json="projects_fast.json"
else
  prj_json="projects.json"
fi

# we do not want the environment to be contaminated with
# user aliases.
# unalias -m '*' # unset all alias

function error() {
  log_message $1 "error"
  exit 1
}


function init() {
  TIMESTAMP=$(date +%Y%m%d%H%M%S)
  EVAL_DIR=$EVAL_DIR_ROOT/$TIMESTAMP
  mkdir -p $EVAL_DIR
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
  count_total=$(jq '[.benchmarks[]] | length' $prj_json)
  log_message "using json $prj_json" "info"
  for ((i = 0; i < $count_total; i++)); do
    current_benchmark=$(jq -r ".benchmarks[$i]" $prj_json)
    enable=$(jq -r '.enable' <<< $current_benchmark)
    if [ "$enable" = "false" ]; then
      #Skipping the banchmark if not enabled
      continue
    fi
    name=$(jq '.name' <<< $current_benchmark)
    log_message "evaluating $name with $N_OUTER_ITER outer iterations..." "info"
    # for i in $(seq 1 $N_OUTER_ITER); do
    #   echo "$i"
    # done
  done
}


# steps
# - clean up artifacts from previous runs
#   - should a run write over resuls of previous run?
# - compile extendj and produce jar
# - set project in state to be prepared for evaluation run


init
# build
run-eval
clean
