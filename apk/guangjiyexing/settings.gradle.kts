import org.gradle.api.initialization.resolve.RepositoriesMode

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        flatDir {
            dirs("app/libs")
        }
        google()
        mavenCentral()
        // AnyThink (Core and adapters)
        maven {
            url = uri("https://jfrog.takuad.com/artifactory/china_sdk")
        }
        // Pangle / Csj
        maven {
            url = uri("https://artifact.bytedance.com/repository/pangle")
        }
    }
}

rootProject.name = "IdiomQuiz"
include(":app")
