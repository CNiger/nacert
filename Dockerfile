FROM continuumio/miniconda3

RUN apt-get update && \
    apt-get install -y libosmesa6 && \
    rm -rf /var/lib/apt/lists/*

RUN conda create -n cadenv -c conda-forge \
    python=3.9 \
    cadquery=2.3 \
    pythonocc-core=7.7.0 \
    fastapi \
    uvicorn \
    ezdxf \
    scipy \
    numpy \
    -y

RUN conda run -n cadenv pip install trimesh

SHELL ["conda", "run", "-n", "cadenv", "/bin/bash", "-c"]

WORKDIR /app

COPY . .

# как у всех сервисов - каждый со своим temp
RUN mkdir -p rot_cut/temp rot_cut/static rot_cut/primitives \
             pol_cut/temp pol_cut/static \
             sek/temp sek/static sek/primitives \
             ras/temp ras/static \
             check/temp check/static \
             temp

EXPOSE 8000

CMD ["conda", "run", "-n", "cadenv", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
