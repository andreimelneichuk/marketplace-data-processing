from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_host: str
    database_port: str
    database_user: str
    database_password: str
    database_name: str

    elasticsearch_host: str
    elasticsearch_port: str

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}\
            @{self.database_host}:{self.database_port}/{self.database_name}"

    @property
    def elasticsearch_url(self) -> str:
        return f"http://{self.elasticsearch_host}:{self.elasticsearch_port}"

    class Config:
        env_file = ".env"


settings = Settings()
