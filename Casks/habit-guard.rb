# Created by scripts/make_package_manifests.py from packaging/templates; do not edit by hand.
cask "habit-guard" do
  version "0.2.0"
  sha256 "ba998d2262e41ce0be4919a635897837edcd2f2f3d2d289ee3d7b7f79539e52b"

  url "https://github.com/bugraskl/habit-guard/releases/download/v#{version}/HabitGuard-#{version}-macos-arm64.dmg"
  name "Habit Guard"
  desc "Catches nail biting and similar habits through your webcam"
  homepage "https://bugraskl.github.io/habit-guard/"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on arch: :arm64
  depends_on macos: :sonoma

  app "Habit Guard.app"

  zap trash: [
    "~/Library/Application Support/habit-guard",
    "~/Library/LaunchAgents/io.github.bugraskl.habit-guard.plist",
  ]

  caveats <<~EOS
    Habit Guard is not signed with an Apple Developer ID yet. If macOS refuses to open it, right-click
    the app in Applications, choose Open, and allow the camera when asked.
  EOS
end
