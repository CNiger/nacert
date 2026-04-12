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
    -y

SHELL ["conda", "run", "-n", "cadenv", "/bin/bash", "-c"]

WORKDIR /app

COPY . .

RUN mkdir -p rot_cut/temp rot_cut/static rot_cut/primitives

EXPOSE 8000

# ЗАПУСКАЕМ НАПРЯМУЮ rot_cut, а не app.py
CMD ["conda", "run", "-n", "cadenv", "uvicorn", "rot_cut.main:app", "--host", "0.0.0.0", "--port", "8000"]
