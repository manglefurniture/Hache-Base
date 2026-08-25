# Estructura recomendada de proyecto

Hache-Base no obliga a usar un framework específico. Esta estructura sirve como referencia para proyectos PHP sencillos que necesiten crecer sin mezclar responsabilidades.

```text
project/
├── public/
│   ├── index.php
│   └── assets/
├── src/
│   ├── Auth/
│   ├── Domain/
│   ├── Services/
│   ├── Repositories/
│   ├── Http/
│   └── Common/
├── config/
├── database/
│   └── migrations/
├── integrations/
├── tests/
│   ├── static/
│   ├── smoke/
│   ├── integration/
│   └── fixtures/
├── deployment/
├── docs/
├── .env.example
└── README.md
```

## Responsabilidades

- `public/`: único punto directamente expuesto por el servidor web cuando sea posible.
- `src/Auth/`: identidad, sesión y autorización.
- `src/Domain/`: conceptos y reglas del negocio.
- `src/Services/`: casos de uso y coordinación de operaciones.
- `src/Repositories/`: persistencia y consultas.
- `src/Http/`: controladores, requests y respuestas.
- `src/Common/`: utilidades realmente genéricas.
- `config/`: carga de configuración; secretos reales fuera del repositorio.
- `database/migrations/`: evolución versionada del esquema.
- `integrations/`: servicios externos desacoplados.
- `tests/`: comprobaciones automatizadas.
- `deployment/`: scripts operativos sin credenciales embebidas.
- `docs/`: arquitectura y reglas específicas del proyecto.

## Regla de crecimiento

No crear capas vacías solo por seguir el diagrama. Separar una responsabilidad cuando su mezcla haga difícil autorizar, probar, reutilizar o modificar el código con seguridad.
