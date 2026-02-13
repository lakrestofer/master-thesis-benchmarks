# Artifact Evaluation: Efficient Demand Evaluation of Fixed-Point Attributes Using Static Analysis

<p float="left" align="center">
<a href="https://www.acm.org/binaries/content/gallery/acm/publications/artifact-review-v1_1-badges/artifacts_evaluated_functional_v1_1.pngl">
  <img  width="100"  src="https://www.acm.org/binaries/content/gallery/acm/publications/artifact-review-v1_1-badges/artifacts_evaluated_functional_v1_1.png"> </a>
  <a href="https://www.acm.org/binaries/content/gallery/acm/publications/artifact-review-v1_1-badges/artifacts_available_v1_1.png"><img width="100"  src="https://www.acm.org/binaries/content/gallery/acm/publications/artifact-review-v1_1-badges/artifacts_available_v1_1.png"> </a>
</p>

**Authors:**

- Idriss Riouak (idriss.riouak@cs.lth.se), Lund University, Sweden
- Niklas Fors (niklas.fors@cs.lth.se), Lund University, Sweden
- Jesper Öqvist (jesper.oqvist@cognibotics.com ), Cognibotics AB,
  Sweden
- Görel Hedin (gorel.hedin@cs.lth.se), Lund University, Sweden
- Christoph Reichenbach (christoph.reichenbach@cs.lth.se), Lund
  University, Sweden

**DOI**:
[10.5281/zenodo.13365896](https://doi.org/10.5281/zenodo.13365896)
**Link to the Paper**:
[Efficient Demand Evaluation of Fixed-Point Attributes Using Static Analysis](https://dl.acm.org/doi/10.1145/3687997.3695644)

## Overview

This document describes the artifact evaluation process for the paper
titled **Efficient Demand Evaluation of Fixed-Point Attributes Using
Static Analysis** submitted to SLE 2024. This document includes
details on how to reproduce the experiments described in the paper,
how to build the tool from source, and how to browse the source code
of the tool and the benchmarks used in the paper.

## Directory Structure

The artifact directory is structured as follows:

```plaintext
RS-Artifact/
├── data/evaluation                             #
│   ├── intraj/                                 # (used for case study 2)
│   │   ├── build.gradle                        #
│   │   ├── src/                                #
│   │   └── tools/                              #
│   │       └── jastadd2.jar                    # (latest Jastadd2 version)
│   ├── CFG/                                    # (used for case study 1)
│   │   ├── run_cfg.sh                          # (script to run the evaluation. It is called by eval.sh)
│   │   ├── tools/                              #
│   │   │   ├── jastadd2.jar                    # (latest Jastadd2 version)
│   │   │   └── jastadd2_old.jar                # (Jastadd2 used to evaluate OldBasicStacked)
│   │   ├── src/                                #
│   ├── extendj_eval/                           # (used for case study 3 and as a benchmark)
│   ├── cat/                                    # (generates callgraph and detects NonCircular Attribtues)
│   ├── antlr-2.7.2/                            #
│   ├── ...                                     # remaining benchmarks
│   ├── results/                                # (contains the results of the evaluation)
│   ├── eval.sh                                 # (main script to run the evaluation)
│   ├── genlatex.py                             # (Generates latex tables. It is called by eval.sh)
│   └── projects.json                           # (contains meta-information about the benchmarks)
├── imgs/                                       # (contains screenshots)
├── Dockerfile.tex                              # (Dockerfile to build the docker image)
├── relaxedstacked-sle2024-amd64.tag.gz         # (Docker image for x86 architecture)
├── relaxedstacked-sle2024-arm64_v8.tag.gz      # (Docker image for ARM architecture)
├── README.md                                   # (this file)
└── README.txt                                  # (a text version of this file)
```

## Docker

In this section, we provide instructions on how to set up and run the
Docker image containing the artifact. The following document was
created using the Docker version `27.1.1 build 6312585`.

### Installing Docker

Before proceeding, ensure Docker is installed on your computer. You
can download it and find installation instructions for various
operating systems including Windows, Mac, and several Linux
distributions at [Docker's official website](https://www.docker.com/).

After installation, you may need to restart your computer. On Windows,
a double restart might be necessary: once after installing Docker
Desktop and once after setting up the Windows Subsystem for Linux
(WSL).

### Starting Docker

Once Docker is installed, begin by starting it up. In some guides, you
may find the terms "start Docker" and "start the Docker Daemon" used
interchangeably. For general purposes, they mean the same thing.
Typically, for most users, starting Docker involves launching Docker
Desktop.

However, it is possible to run Docker without Docker Desktop, so the
commands to start Docker might vary based on your setup.

### Verifying Docker Installation

To confirm that Docker is running correctly on your system, open a
command prompt and enter the following command:

    docker run --rm hello-world

You should see output similar to the following:

> Unable to find image 'hello-world:latest' locally latest: Pulling
> from library/hello-world 478afc919002: Pull complete Digest:
> sha256:a26bff933ddc26... Status: Downloaded newer image for
> hello-world:latest
>
> Hello from Docker! This message shows that your installation appears
> to be working correctly.

This command will provide you with information about your Docker
installation and indicate whether it is running properly.

If you encounter permission issues when executing Docker commands, you
may need to prepend `sudo` to each command. If this approach fails, it
is possible the Docker installation was not completed correctly. For a
list of frequent issues and their resolutions, visit
[Docker's documentation](https://docs.docker.com/).

### Getting the Docker image (Recommended way of running the experiments)

The artifact includes a Docker image that provides the following
functionalities:

- Run the experiments described in the paper.
- Build the tool described in the paper.
- Browse the source code of the tool and the benchmarks used in the
  paper.

The Docker image is based on the Ubuntu 22.04 image and contains all
the necessary dependencies to run the experiments.

We distinguish between two types of commands: `[host]` commands and
`[docker]` commands.

- `#[host]` commands should be executed on your host machine.
- `#[docker]` commands should be executed inside the Docker container.

You can download a pre-built image from the following link:
[https://someurl](https://someurl).

Note that there are two images available: one for the x86 architecture
and one for the ARM architecture.

| **Image Name**                         | **Architecture** |
| -------------------------------------- | ---------------- |
| relaxedstacked-sle2024-amd64.tag.gz    | x86              |
| relaxedstacked-sle2024-arm64_v8.tag.gz | ARM              |

If you download an image that is not compatible with your system's
architecture, Docker can still run it using emulation, but this may
significantly reduce performance. For instance, if you attempt to run
an amd64 image on an M1 CPU (which is arm-based), Docker will issue
the following warning:

> WARNING: The requested image's platform (linux/amd64) does not match
> the detected host platform (linux/arm64/v8) and no specific platform
> was requested

Once you have downloaded the image, you can load it into Docker using
the following command:

    #[host]
    docker load -i relaxedstacked-sle2024-amd64.tag.gz

relaxedstacked-sle2024-arm64v8 If you downloaded the ARM image, you
can load it into Docker using the following command:

    #[host]
    docker load -i relaxedstacked-sle2024-arm64_v8.tag.gz

### Build the Docker image locally

You can also build the Docker image locally by running the following
command:

    #[host]
    cd path/to/artifact/dir
    docker build -t relaxedstacked:SLE2024 .

By default, the Docker image is built for the x86 architecture. If you
want to build the image for the ARM architecture, you can run the
following command:

    #[host]
    cd path/to/artifact/dir
    docker build -t relaxedstacked:SLE2024 --build-arg BASE_IMAGE=arm64v8/ubuntu:22.04 .

### Running the Docker image

Create a container from the image using the following command:

    #[host]
    docker run -p 8080:8080 -it relaxedstacked:SLE2024

Your terminal should now be inside the Docker container. You can now
run the experiments described in the paper, build the tool, and browse
the source code of the tool and the benchmarks used in the paper. The
default user in the container is `SLE2024` and the password is
`SLE2024`.

If you close the terminal and want to re-enter the container, you can
run the following command:

    #[host]
    docker start $(docker container ls -aq --filter ancestor=relaxedstacked:SLE2024) -i
    docker exec -it $(docker container ls -aq --filter ancestor=relaxedstacked:SLE2024) /bin/bash

Once inside the container, you can either browse the source code or
run the experiments. Once you are done with the container, you can
exit it by running the following command:

    #[host]
    exit

### Run the experiments in Docker

#### Kick the tires

First, you need to navigate to the evaluation directory: #[docker] cd
data/evaluation

Then you can run the experiments by executing the `eval.sh` script.
Run the script with the following command:

    #[docker]
    sudo zsh eval.sh fast

This will collect two data points for two benchmarks: `antlr` and
`pmd`.

> ℹThis process took around 20 minutes on a MacBook Pro with an M1 Pro
> chip.

If no errors are reported, you can check the results by running the
following command:

    #[host]
    docker cp $(docker container ls --filter ancestor=relaxedstacked:SLE2024 -aq):/data/results.pdf destination/folder/

where `destination/folder/` is the path to the folder where you want
to save the results.

> ⚠️The results are not representative as few data points are
> collected and few steady-state iterations are run.

#### Run the full set of experiments

If no errors are reported, you can run the full set of experiments by
executing the following command:

    #[docker]
    sudo zsh eval.sh 25 50

Where the first argument is the number of start-up iterations and the
second argument is the number of steady-state iterations.

In our case, the experiments took around more than 2 days to complete
with a very powerful machine. We would recommend reducing the number
of iterations if you are running the experiments on a machine with
fewer resources. We believe that running the experiments with 10
start-up iterations and 25 steady-state iterations should be
sufficient to get meaningful results.

    #[docker]
    sudo zsh eval.sh 10 15

## Run the artifact without Docker

If you want to build the tool from source, you can do so by following
the instructions in this section.

### Requirements

In order to build the tool, you need to have the following
dependencies installed on your machine:

- **zsh** (tested with zsh v5.9)
- **python3.9** (tested with Python 3.12.2)
- **python3-pip** (tested with pip 24.0)
- **openjdk-8-jdk** (8.0.372.fx-zulu)
- **openjdk-11-jdk** (11.0.22)
- **openjfx** (included in the openjdk-8-jdk package)
- **pdflatex** (tested with pdfTeX 3.141592653-2.6-1.40.25 (TeX Live
  2023))
- **timeout** (tested with timeout from GNU coreutils 9.5)

To run the Python scripts, you need to install the following Python
packages:

- **numpy** (tested with numpy 1.26.4)
- **pandas** (tested with pandas 2.2.1)
- **matplotlib** (tested with matplotlib 3.8.4)
- **seaborn** (tested with seaborn 0.13.2)
- **scipy** (tested with scipy 1.13.0)

### Run the experiments

Navigate to the evaluation directory:

    cd data/evaluation

Then you can run the experiments by executing the `eval.sh` script.
The script takes two arguments: the number of start-up iterations and
the number of steady-state iterations (a comprehensive explanation of
the script is provided in Section 3). We recommend running one
start-up iteration and one steady-state iteration to get a feel for
the experiments and to check that everything is working as expected.

    # [host]
    sudo zsh eval.sh 1 1

If no errors are reported, you can run the full set of experiments by
executing the following command: # [host] sudo zsh eval.sh 25 50

In our case, the experiments took more than 2 days to complete. We
would recommend reducing the number of iterations if you are running
the experiments on a machine with fewer resources. We believe that
running the experiments with 10 start-up iterations and 25
steady-state iterations should be sufficient to get meaningful
results.

    # [host]
    sudo zsh eval.sh 10 25

## Read the results

Once the experiments are completed, all the raw results are stored in
the folder `evaluation/results/YYYYMMDDHHMMSS`, where `YYYYMMDDHHMMSS`
is the timestamp when the experiments were started. A summary of the
results is stored in the PDF file
`evaluation/results/YYYYMMDDHHMMSS/results.pdf`. The summary contains
the table for all the case studies and the graphs for the performance
evaluation presented in the original paper, with references to the
corresponding tables and figures in the paper. A copy of the PDF of
the latest results is also stored in `data` to facilitate access to
the results.

If you are running the experiments on Docker and want to save the
results to your host machine, you can run the following command:

    #[host]
    docker cp $(docker container ls --filter ancestor=relaxedstacked:SLE2024 -aq):/data/results.pdf destination/folder/

Where `destination/folder/` is the path to the folder where you want
to save the results.

## Reduce Execution Time

We can act on three fronts to reduce the execution time of the
artifact evaluation:

1. Reduce the number of start-up iterations.
2. Reduce the number of steady-state iterations.
3. Reduce the number of benchmarks.

The first two points were already discussed in Sections
[Build the Tool from Source](#sec:build) and [Docker](#sec:docker).

To reduce the number of benchmarks, you can exclude some of the
benchmarks from the evaluation. The benchmarks are located in the
`evaluation` directory, and all the meta-information is located in a
file called `projects.json`.

The `projects.json` file is located in the `evaluation/` directory.

This file contains all the necessary information about the benchmarks,
such as the name, the path, the number of methods, and the number of
lines of code. For example, the meta information for the benchmark
`antlr` is as follows:

    {
        "name": "antlr-2.7.2",
        "url": "https://www.antlr2.org/download/antlr-2.7.2.zip",
        "checkout": "wget",
        "description": "ANTLR is an extensible, dynamic parser generator",
        "version": "2.7.2",
        "commit": "",
        "classpath": "antlr-2.7.2",
        "dir_to_analyze": "antlr/",
        "exclude_dirs": [
            {
                "path": "examples/",
                "motivation": "Contains examples."
            }
        ],
        "LOC": 36525,
        "enable": true,
        "methods": 2070,
        "entryPackage": "antlr.Tool",
        "entryMethod": "main"
    }

To exclude a benchmark from the evaluation, set the `enable` field to
`false`.

### Tools, Dependencies and External Repositories

The artifact is based on the following tools and dependencies:

- **JastAdd2 (70cf0bc)**: a Reference Attribute Grammar (RAG) system
  that is used to generate the *IntraJ* and *ExtendJ* tools. In this
  artifact we used the latest version of *JastAdd2* available at the
  time of writing this document.
  [Link](https://Idriss_Rio@bitbucket.org/Idriss_Rio/jastadd.git).

- **JastAdd2_old**: an older version of *JastAdd2* that was used to
  generate the *OldBasicStacked* tool.
  [Link](https://bitbucket.org/jastadd/crag-artifact/src/master/).

- **ExtendJ (v.11.0)**: a Java compiler that is used both as a
  benchmark and as a case study in the paper.
  [Link](https://bitbucket.org/extendj/extendj/src/master/). The
  article about this tool is available at
  [Link](https://dl.acm.org/doi/10.1145/1297105.1297029).

- **IntraJ (commit #207874a)**: a static analysis tool that is used to
  evaluate the performance of the proposed demand-driven evaluation of
  fixed-point attributes. [Link](https://github.com/lu-cs-sde/IntraJ).
  The article about this tool is available at
  [Link](https://ieeexplore.ieee.org/document/9610697/metrics#metrics).

- **CAT (commit #f2a639b)**: call-graph analysis tool that is used to
  generate the meta-information about strongly connected components
  between attributes. [Link](https://github.com/IdrissRio/cat).

- **CFG**: artifact of the LL(1) parser construction case study.
  [Link](https://bitbucket.org/jastadd/crag-artifact/src/master/). The
  article about this artifact is available at
  [Link](https://www.sciencedirect.com/science/article/pii/S0167642307000767?via%3Dihub).

- The following benchmarks are used in the evaluation of the paper:
  - **commons-cli *v.1.5***
  - **jackson-dataformat *commit #1842f1e***
  - **commons-jxpath *v.1.3***
  - **antlr *v.2.7.2***
  - **jackson-core *commit #c5b123b***
  - **pmd *v.4.2.5***
  - **struts *v.2.3.22***
  - **joda-time *v.2.10.13***
  - **jfreechart *v.1.0.0***
  - **fop *v.0.95***
  - **castor *v.1.3.3***
  - **weka *revision #7806***

# Appendix: Visualise the Callgraph (Not essential for the evaluation but nice to have for CallGraph visualization)

### Visualise the Callgraph

The callgraph is a directed graph that represents the call
relationships between methods in the program. You can visualise the
callgraph of the LL(1) parser, *IntraJ*, and *ExtendJ* by using *CAT*.

Navigate to the `evaluation` directory:

    #[host] or [docker]
    cd data/evaluation

#### LL(1) Parser's Callgraph

To visualise the callgraph of the LL(1) parser, run the following
command:

    # [host] or [docker]
    sudo zsh run_cat.sh cfg

The output should be similar to the following:

    [INFO]: Starting call graph generation
    [INFO]: Call graph generation finished
    [INFO]: Starting SCCs computation
    [INFO]: SCCs computation finished
    Number of nodes: 19
    Number of circular nodes: 10
    Number of SCCs with size greater than two: 2
    Mean size of SCCs: 3.0
    Maximum size of SCC: 3
    [INFO]: Call graph saved to CacheConfig.json
    [INFO]: You can visualize the call graph at http://localhost:8080/index.html
    SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".
    SLF4J: Defaulting to no-operation (NOP) logger implementation
    SLF4J: See http://www.slf4j.org/codes.html#StaticLoggerBinder for further details.

You can now visit
[http://localhost:8080/index.html](http://localhost:8080/index.html)
to visualise the callgraph of the LL(1) parser.

![Callgraph of the LL(1) parser with the `Concentric` layout](imgs/cfg.png)

The graph is not easy to read because of the concentric layout. But
the user can still interact with the graph by zooming in and out,
dragging the nodes, and searching for a specific node. The user can
also change the layout by clicking on the `Settings` button and
selecting a different layout.

![Callgraph of the LL(1) parser with the `Cose` layout](imgs/cfg2.png)

#### *IntraJ* and *ExtendJ* Callgraph

To visualise the callgraph of *IntraJ*, run the following command:

    # [host] or [docker]
    sudo zsh run_cat.sh intraj

To visualise the callgraph of *ExtendJ*, run the following command:

    # [host] or [docker]
    sudo zsh run_cat.sh extendj

The output should be similar to the following:

    [INFO]: Starting call graph generation
    [INFO]: Call graph generation finished
    [INFO]: Starting SCCs computation
    [INFO]: SCCs computation finished
    Number of nodes: 2640
    Number of circular nodes: 356
    Number of SCCs with size greater than two: 10
    Mean size of SCCs: 131.1
    Maximum size of SCC: 1010
    [INFO]: Call graph saved to CacheConfiguration.json
    [INFO]: You can visualize the call graph at http://localhost:8080/index.html
    SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".
    SLF4J: Defaulting to no-operation (NOP) logger implementation
    SLF4J: See http://www.slf4j.org/codes.html#StaticLoggerBinder for further details.

You can now visit
[http://localhost:8080/index.html](http://localhost:8080/index.html)
to visualise the callgraph of *IntraJ* and *ExtendJ*.

![Callgraph of *IntraJ* with the `Cose` layout](imgs/intraj.png)

#### Distinguished Artifact Award

The artifact has been evaluated by the Artifact Evaluation Committee
and has been awarded the Distinguished Artifact Award.

<p float="left" align="center">
  <img    src="imgs/distinguished.png">
</p>
