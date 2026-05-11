import subprocess


class ValidationAgent:

    def validate_patch(self):

        try:

            build = subprocess.run(
                ["docker", "build", "-t", "self-healing-validator", "."],
                capture_output=True,
                text=True
            )

            if build.returncode != 0:
                return {
                    "status": "build_failed",
                    "output": build.stderr
                }

            test = subprocess.run(
                ["docker", "run", "--rm", "self-healing-validator"],
                capture_output=True,
                text=True
            )

            if test.returncode == 0:
                return {
                    "status": "success",
                    "output": test.stdout
                }

            return {
                "status": "failed",
                "output": test.stdout + test.stderr
            }

        except Exception as e:
            return {
                "status": "error",
                "output": str(e)
            }