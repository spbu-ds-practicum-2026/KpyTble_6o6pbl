plugins {
  java
  id("org.springframework.boot") version "3.5.16"
}

group = "plotina"
version = "0.0.1-SNAPSHOT"

java{
  toolchain{
    languageVersion = JavaLanguageVersion.of(21)
  }
}

repositories{
  mavenCentral()
}

dependencies{
  implementation(platform("org.springframework.boot:spring-boot-dependencies:3.5.16"))
  implementation("org.springframework.boot:spring-boot-starter-web")
}
